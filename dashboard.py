import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime, timezone, timedelta

from config import BRANDS, TIMEZONE, SCRAPE_HOUR
from database import init_db, get_connection
from scraper import scrape_all
from metrics import (
    get_current_state, get_posting_metrics,
    get_engagement_metrics, get_growth_metrics, compute_scores,
)
from recommendations import generate_recommendations


# ── Scheduler ────────────────────────────────────────────────────────────────

def _start_scheduler():
    from apscheduler.schedulers.background import BackgroundScheduler
    import pytz
    scheduler = BackgroundScheduler()
    scheduler.add_job(scrape_all, "cron", hour=SCRAPE_HOUR,
                      timezone=pytz.timezone(TIMEZONE))
    scheduler.start()
    st.session_state["scheduler_started"] = True


if "scheduler_started" not in st.session_state:
    _start_scheduler()

init_db()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _last_scrape_ts():
    with get_connection() as conn:
        row = conn.execute(
            "SELECT run_at FROM scrape_log ORDER BY run_at DESC LIMIT 1"
        ).fetchone()
    return row["run_at"] if row else "Never"


def _score_color(val):
    if val is None:
        return "background-color: #6b7280; color: white"
    if val < 40:
        return "background-color: #dc2626; color: white"
    if val <= 60:
        return "background-color: #f59e0b; color: white"
    return "background-color: #16a34a; color: white"


def _load_all_metrics(window):
    result = {}
    for name, handle in BRANDS.items():
        result[name] = {
            "posting":    get_posting_metrics(handle, window),
            "engagement": get_engagement_metrics(handle, window),
            "growth":     get_growth_metrics(handle),
            "state":      get_current_state(handle),
        }
    return result


# ── Header ────────────────────────────────────────────────────────────────────

st.title("AKKO Portfolio Instagram Benchmark")
st.caption(f"Last scrape: {_last_scrape_ts()}")

col_btn, col_window = st.columns([1, 3])
with col_btn:
    if st.button("Force refresh now"):
        with st.spinner("Scraping…"):
            scrape_all()
        st.rerun()
with col_window:
    if "window" not in st.session_state:
        st.session_state["window"] = 30
    window = st.radio("Time window (days)", [7, 30, 90],
                      index=[7, 30, 90].index(st.session_state["window"]),
                      horizontal=True)
    st.session_state["window"] = window

page = st.sidebar.radio("Page", ["Portfolio Overview", "Per-Brand Drill-Down"])

all_metrics = _load_all_metrics(window)
scores      = compute_scores(all_metrics)
brand_names = list(BRANDS.keys())


# ── Page 1: Portfolio Overview ────────────────────────────────────────────────

if page == "Portfolio Overview":

    # Row 1: KPI cards
    cols = st.columns(4)
    for i, name in enumerate(brand_names):
        m     = all_metrics[name]
        state = m["state"] or {}
        with cols[i]:
            st.markdown(f"**{name}**")
            st.caption(BRANDS[name])
            st.metric("Followers",          f"{state.get('followers', 0):,}")
            st.metric(f"Posts (last {window}d)", m["posting"]["posts_count"])
            st.metric("Eng. rate",          f"{m['engagement']['engagement_rate'] * 100:.2f}%")

    st.divider()

    # Row 2: Radar chart
    growth_ready = all(all_metrics[b]["growth"]["sufficient_data_for_growth"] for b in brand_names)
    history_min  = min(all_metrics[b]["growth"]["history_days"] for b in brand_names)

    if growth_ready:
        axes = ["Content Velocity", "Engagement Quality", "Growth Momentum"]
        fig  = go.Figure()
        for name in brand_names:
            s    = scores[name]
            vals = [s["content_velocity"] or 0, s["engagement_quality"] or 0, s["growth_momentum"] or 0]
            fig.add_trace(go.Scatterpolar(r=vals + [vals[0]], theta=axes + [axes[0]], name=name))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                          title="Brand Radar")
        st.plotly_chart(fig, use_container_width=True)
    else:
        axes = ["Content Velocity", "Engagement Quality"]
        fig  = go.Figure()
        for name in brand_names:
            s    = scores[name]
            vals = [s["content_velocity"] or 0, s["engagement_quality"] or 0]
            fig.add_trace(go.Scatterpolar(r=vals + [vals[0]], theta=axes + [axes[0]], name=name))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                          title="Brand Radar (2-axis)")
        st.plotly_chart(fig, use_container_width=True)
        st.info(
            f"Growth Momentum requires 14+ days of historical snapshots. "
            f"Currently at {history_min} days."
        )

    st.divider()

    # Row 3: Scoreboard table
    rows = [
        {"Brand": n, "Content Velocity": scores[n]["content_velocity"],
         "Engagement Quality": scores[n]["engagement_quality"],
         "Growth Momentum": scores[n]["growth_momentum"]}
        for n in brand_names
    ]
    df_scores = pd.DataFrame(rows).set_index("Brand")
    score_cols = ["Content Velocity", "Engagement Quality", "Growth Momentum"]
    st.dataframe(
        df_scores.style.map(_score_color, subset=score_cols),
        use_container_width=True,
    )

    st.divider()

    # Row 4: Recommendation cards
    st.subheader("Recommendations")
    for name in brand_names:
        recs = generate_recommendations(name, all_metrics[name], scores[name])
        with st.expander(name, expanded=True):
            for r in recs:
                st.markdown(f"- {r}")


# ── Page 2: Per-Brand Drill-Down ──────────────────────────────────────────────

elif page == "Per-Brand Drill-Down":

    selected = st.selectbox("Brand", brand_names)
    handle   = BRANDS[selected]
    m        = all_metrics[selected]
    posting  = m["posting"]
    eng      = m["engagement"]
    growth   = m["growth"]
    state    = m["state"] or {}

    # Section 1: Metric table
    st.subheader("Metrics")
    metric_rows = [
        ("Followers",       f"{state.get('followers', '—'):,}" if state.get('followers') else "—"),
        ("Posts in window", posting["posts_count"]),
        ("Posts / week",    f"{posting['posts_per_week']:.1f}"),
        ("Reel share",      f"{posting['reel_share'] * 100:.0f}%"),
        ("Carousel share",  f"{posting['carousel_share'] * 100:.0f}%"),
        ("Image share",     f"{posting['image_share'] * 100:.0f}%"),
        ("Avg gap (days)",  f"{posting['avg_gap_days']:.1f}" if posting["avg_gap_days"] else "—"),
        ("Avg caption len", f"{posting['avg_caption_length']:.0f}"),
        ("Avg hashtags",    f"{posting['avg_hashtag_count']:.1f}"),
        ("Avg likes",       f"{eng['avg_likes']:.0f}"),
        ("Avg comments",    f"{eng['avg_comments']:.0f}"),
        ("Engagement rate", f"{eng['engagement_rate'] * 100:.2f}%"),
        ("Avg video views", f"{eng['avg_video_views']:.0f}"),
        ("Reel view rate",  f"{eng['reel_view_rate'] * 100:.2f}%"),
        ("Follower Δ 30d",  growth["follower_delta_30d"] if growth["follower_delta_30d"] is not None else "—"),
        ("Follower Δ 90d",  growth["follower_delta_90d"] if growth["follower_delta_90d"] is not None else "—"),
        ("History (days)",  growth["history_days"]),
    ]
    st.dataframe(
        pd.DataFrame(metric_rows, columns=["Metric", "Value"]),
        use_container_width=True, hide_index=True,
    )

    st.divider()

    # Section 2: Posting heatmap
    st.subheader("Posting Heatmap")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=window)).isoformat()
    with get_connection() as conn:
        df_heat = pd.read_sql_query(
            "SELECT posted_at FROM posts WHERE handle = ? AND posted_at >= ?",
            conn, params=(handle, cutoff),
        )

    if df_heat.empty:
        st.info("No posts in selected window.")
    else:
        df_heat["posted_at"] = pd.to_datetime(df_heat["posted_at"], utc=True)
        df_heat["dow"]  = df_heat["posted_at"].dt.dayofweek
        df_heat["hour"] = df_heat["posted_at"].dt.hour
        heat = df_heat.groupby(["dow", "hour"]).size().reset_index(name="count")
        pivot = (heat.pivot(index="dow", columns="hour", values="count")
                     .reindex(index=range(7), columns=range(24))
                     .fillna(0))
        pivot.index = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        fig_h = px.imshow(pivot, labels=dict(x="Hour", y="Day", color="Posts"),
                          title="Posts by Day × Hour", color_continuous_scale="Blues")
        st.plotly_chart(fig_h, use_container_width=True)

    st.divider()

    # Sections 3 & 4: Top / Bottom 3 posts
    with get_connection() as conn:
        df_all = pd.read_sql_query(
            "SELECT * FROM posts WHERE handle = ? AND posted_at >= ?",
            conn, params=(handle, cutoff),
        )

    def _post_table(df_sub):
        df_sub = df_sub.copy()
        df_sub["link"]            = df_sub["shortcode"].apply(lambda s: f"https://www.instagram.com/p/{s}/")
        df_sub["caption_excerpt"] = df_sub["caption"].str[:80]
        return df_sub[["posted_at", "media_type", "likes", "comments", "caption_excerpt", "link"]]

    if not df_all.empty:
        df_all["engagement"] = df_all["likes"] + df_all["comments"]

        st.subheader("Top 3 Posts")
        st.dataframe(_post_table(df_all.nlargest(3, "engagement")),
                     use_container_width=True, hide_index=True)

        st.subheader("Bottom 3 Posts")
        candidates = df_all[df_all["engagement"] > 0] if len(df_all[df_all["engagement"] > 0]) > 3 else df_all
        st.dataframe(_post_table(candidates.nsmallest(3, "engagement")),
                     use_container_width=True, hide_index=True)
    else:
        st.info("No posts in selected window.")

    st.divider()

    # Section 5: Follower trend
    st.subheader("Follower Trend")
    with get_connection() as conn:
        df_trend = pd.read_sql_query(
            "SELECT scraped_at, followers FROM profile_snapshots WHERE handle = ? ORDER BY scraped_at",
            conn, params=(handle,),
        )

    if df_trend.empty:
        st.info("No snapshot history yet.")
    else:
        df_trend["scraped_at"] = pd.to_datetime(df_trend["scraped_at"], utc=True)
        fig_t = px.line(df_trend, x="scraped_at", y="followers",
                        title="Follower Count Over Time")
        st.plotly_chart(fig_t, use_container_width=True)
