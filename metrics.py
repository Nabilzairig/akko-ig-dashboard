import pandas as pd
from datetime import datetime, timezone, timedelta

from database import get_connection, get_latest_snapshot, get_oldest_snapshot_within


def get_current_state(handle):
    return get_latest_snapshot(handle)


def get_posting_metrics(handle, days):
    """Return posting cadence metrics for handle over the last `days` days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with get_connection() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM posts WHERE handle = ? AND posted_at >= ?",
            conn, params=(handle, cutoff),
        )

    if df.empty:
        return {
            "posts_count": 0, "posts_per_week": 0.0,
            "reel_share": 0.0, "carousel_share": 0.0, "image_share": 0.0,
            "avg_gap_days": None, "avg_caption_length": 0.0, "avg_hashtag_count": 0.0,
        }

    n = len(df)
    df["posted_at"] = pd.to_datetime(df["posted_at"], utc=True)
    df = df.sort_values("posted_at")
    gaps = df["posted_at"].diff().dropna().dt.total_seconds() / 86400

    return {
        "posts_count": n,
        "posts_per_week": n / (days / 7),
        "reel_share": float((df["media_type"] == "reel").sum() / n),
        "carousel_share": float((df["media_type"] == "carousel").sum() / n),
        "image_share": float((df["media_type"] == "image").sum() / n),
        "avg_gap_days": float(gaps.mean()) if len(gaps) > 0 else None,
        "avg_caption_length": float(df["caption_length"].mean()),
        "avg_hashtag_count": float(df["hashtag_count"].mean()),
    }


def get_engagement_metrics(handle, days):
    """Return engagement metrics for handle over the last `days` days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with get_connection() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM posts WHERE handle = ? AND posted_at >= ?",
            conn, params=(handle, cutoff),
        )

    snapshot = get_latest_snapshot(handle)
    followers = (snapshot["followers"] or 1) if snapshot else 1

    if df.empty:
        return {
            "avg_likes": 0.0, "avg_comments": 0.0,
            "engagement_rate": 0.0, "avg_video_views": 0.0, "reel_view_rate": 0.0,
        }

    avg_likes    = float(df["likes"].mean())
    avg_comments = float(df["comments"].mean())
    reels        = df[df["media_type"] == "reel"]
    avg_video_views = float(reels["video_views"].mean()) if not reels.empty else 0.0

    return {
        "avg_likes": avg_likes,
        "avg_comments": avg_comments,
        "engagement_rate": (avg_likes + avg_comments) / followers,
        "avg_video_views": avg_video_views,
        "reel_view_rate": avg_video_views / followers,
    }


def get_growth_metrics(handle):
    """Return follower growth deltas and data-sufficiency flag for handle."""
    snapshot = get_latest_snapshot(handle)
    if not snapshot:
        return {
            "follower_delta_30d": None, "follower_growth_pct_30d": None,
            "follower_delta_90d": None, "follower_growth_pct_90d": None,
            "sufficient_data_for_growth": False, "history_days": 0,
        }

    with get_connection() as conn:
        first_row = conn.execute(
            "SELECT scraped_at FROM profile_snapshots WHERE handle = ? ORDER BY scraped_at ASC LIMIT 1",
            (handle,),
        ).fetchone()

    first_dt = datetime.fromisoformat(first_row["scraped_at"])
    if first_dt.tzinfo is None:
        first_dt = first_dt.replace(tzinfo=timezone.utc)
    history_days      = (datetime.now(timezone.utc) - first_dt).days
    current_followers = snapshot["followers"] or 0

    def _delta(days):
        old = get_oldest_snapshot_within(handle, days)
        if not old:
            return None, None
        old_f = old["followers"] or 0
        delta = current_followers - old_f
        pct   = (delta / old_f * 100) if old_f > 0 else None
        return delta, pct

    d30, p30 = _delta(30)
    d90, p90 = _delta(90)

    return {
        "follower_delta_30d":      d30,
        "follower_growth_pct_30d": p30,
        "follower_delta_90d":      d90,
        "follower_growth_pct_90d": p90,
        "sufficient_data_for_growth": history_days >= 14,
        "history_days": history_days,
    }


def _normalize(values):
    """Min-max normalize to [0, 1]; returns 0.5 for all when min == max."""
    filtered = [v for v in values if v is not None]
    if not filtered:
        return [0.5] * len(values)
    mn, mx = min(filtered), max(filtered)
    if mn == mx:
        return [0.5 if v is not None else None for v in values]
    return [(v - mn) / (mx - mn) if v is not None else None for v in values]


def compute_scores(all_brand_metrics):
    """
    Compute Content Velocity, Engagement Quality, Growth Momentum (0-100)
    for each brand via min-max normalization across the portfolio.
    """
    brands = list(all_brand_metrics.keys())

    # Content Velocity
    ppw   = [all_brand_metrics[b]["posting"]["posts_per_week"] for b in brands]
    rs    = [all_brand_metrics[b]["posting"]["reel_share"]     for b in brands]
    ppw_n = _normalize(ppw)
    raw_cv = [ppw_n[i] * (1 + rs[i]) if ppw_n[i] is not None else None
              for i in range(len(brands))]
    cv_n  = _normalize(raw_cv)
    cv_scores = [round(v * 100) if v is not None else None for v in cv_n]

    # Engagement Quality
    er    = [all_brand_metrics[b]["engagement"]["engagement_rate"] for b in brands]
    rvr   = [all_brand_metrics[b]["engagement"]["reel_view_rate"]  for b in brands]
    er_n  = _normalize(er)
    rvr_n = _normalize(rvr)
    has_reel = any(v and v > 0 for v in rvr)
    eq_scores = []
    for i in range(len(brands)):
        a     = er_n[i]  or 0
        b_val = rvr_n[i] or 0
        eq_scores.append(
            round((a * 0.7 + b_val * 0.3) * 100) if has_reel else round(a * 100)
        )

    # Growth Momentum
    if not all(all_brand_metrics[b]["growth"]["sufficient_data_for_growth"] for b in brands):
        gm_scores = [None] * len(brands)
    else:
        p30   = [all_brand_metrics[b]["growth"]["follower_growth_pct_30d"] for b in brands]
        p90   = [all_brand_metrics[b]["growth"]["follower_growth_pct_90d"] for b in brands]
        p30_n = _normalize(p30)
        has_90 = any(v is not None for v in p90)
        if not has_90:
            gm_scores = [round(v * 100) if v is not None else None for v in p30_n]
        else:
            p90_n = _normalize(p90)
            gm_scores = [
                round(((p30_n[i] or 0) * 0.4 + (p90_n[i] or 0) * 0.6) * 100)
                for i in range(len(brands))
            ]

    return {
        brands[i]: {
            "content_velocity":  cv_scores[i],
            "engagement_quality": eq_scores[i],
            "growth_momentum":   gm_scores[i],
        }
        for i in range(len(brands))
    }
