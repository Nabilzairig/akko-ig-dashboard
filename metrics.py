import pandas as pd
from datetime import datetime, timezone

from database import get_connection, get_latest_snapshot, get_oldest_snapshot_within


def get_current_state(handle):
    return get_latest_snapshot(handle)


def get_posting_metrics(handle, start_iso, end_iso):
    """Return posting cadence metrics for handle over the [start_iso, end_iso] window."""
    with get_connection() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM posts WHERE handle = ? AND posted_at >= ? AND posted_at <= ?",
            conn, params=(handle, start_iso, end_iso),
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

    start_dt = datetime.fromisoformat(start_iso)
    end_dt   = datetime.fromisoformat(end_iso)
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)
    days = max((end_dt - start_dt).days, 1)

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


def get_engagement_metrics(handle, start_iso, end_iso):
    """Return engagement metrics for handle over the [start_iso, end_iso] window."""
    with get_connection() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM posts WHERE handle = ? AND posted_at >= ? AND posted_at <= ?",
            conn, params=(handle, start_iso, end_iso),
        )

    snapshot = get_latest_snapshot(handle)
    followers = (snapshot["followers"] or 1) if snapshot else 1

    if df.empty:
        return {
            "avg_likes": 0.0, "avg_comments": 0.0,
            "engagement_rate": 0.0, "avg_video_views": 0.0, "reel_view_rate": 0.0,
        }

    avg_likes       = float(df["likes"].mean())
    avg_comments    = float(df["comments"].mean())
    reels           = df[df["media_type"] == "reel"]
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
            "follower_delta_7d":  None, "follower_growth_pct_7d":  None,
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

    d7,  p7  = _delta(7)
    d30, p30 = _delta(30)
    d90, p90 = _delta(90)

    return {
        "follower_delta_7d":       d7,
        "follower_growth_pct_7d":  p7,
        "follower_delta_30d":      d30,
        "follower_growth_pct_30d": p30,
        "follower_delta_90d":      d90,
        "follower_growth_pct_90d": p90,
        "sufficient_data_for_growth": history_days >= 14,
        "history_days": history_days,
    }


def get_growth_delta_for_range(handle, start_iso, end_iso):
    """
    Return (delta, pct) follower change between the snapshots nearest to
    start_iso and end_iso. Returns (None, None) when no snapshots exist.
    """
    from database import get_snapshot_nearest
    snap_start = get_snapshot_nearest(handle, start_iso)
    snap_end   = get_snapshot_nearest(handle, end_iso)
    if not snap_start or not snap_end:
        return None, None
    f_start = snap_start["followers"] or 0
    f_end   = snap_end["followers"]   or 0
    delta   = f_end - f_start
    pct     = (delta / f_start * 100) if f_start > 0 else None
    return delta, pct


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
