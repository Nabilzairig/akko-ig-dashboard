import threading
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime, timezone, timedelta, time as dtime

from config import BRANDS, TIMEZONE, SCRAPE_HOUR
from database import init_db, get_connection
from scraper import scrape_all
from metrics import (
    get_current_state, get_posting_metrics,
    get_engagement_metrics, get_growth_metrics, compute_scores,
    get_growth_delta_for_range,
)
from recommendations import generate_recommendations


# ── Brand palette ─────────────────────────────────────────────────────────────

BRAND_COLORS = {
    "Mandi":    "#833AB4",
    "Fancy":    "#FD1D1D",
    "Elephant": "#FCAF45",
    "Add-Me":   "#405DE6",
}

# ── CSS ───────────────────────────────────────────────────────────────────────

_CSS = """
<style>
/* KPI metric cards */
div[data-testid="metric-container"] {
    background: white;
    border-radius: 12px;
    padding: 16px 20px 12px 20px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.09);
    border-top: 3px solid #833AB4;
    margin-bottom: 8px;
}

/* Section headers */
h2, h3 { color: #1a1a2e; }

/* Sidebar */
section[data-testid="stSidebar"] { background: #1a1a2e; }
section[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
section[data-testid="stSidebar"] .stRadio label { color: #e0e0e0 !important; }

/* Dividers */
hr { border-color: #E5E7EB; margin: 1.2rem 0; }

/* Quick preset buttons — pill style */
div[data-testid="stButton"] > button {
    border-radius: 20px;
    padding: 4px 16px;
    font-size: 0.82rem;
    font-weight: 600;
}

/* Date picker max-width */
div[data-testid="stDateInput"] { max-width: 360px; }
</style>
"""


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


def _load_all_metrics(start_iso, end_iso):
    result = {}
    for name, handle in BRANDS.items():
        result[name] = {
            "posting":    get_posting_metrics(handle, start_iso, end_iso),
            "engagement": get_engagement_metrics(handle, start_iso, end_iso),
            "growth":     get_growth_metrics(handle),
            "state":      get_current_state(handle),
        }
    return result


# ── Header ────────────────────────────────────────────────────────────────────

st.markdown(_CSS, unsafe_allow_html=True)
st.title("AKKO Portfolio Instagram Benchmark")
st.caption(f"Last scrape: {_last_scrape_ts()}")

today = datetime.now(timezone.utc).date()

# Quick preset buttons
col_btn, col_7, col_30, col_90 = st.columns([2, 1, 1, 1])
with col_btn:
    if st.button("⟳ Force refresh"):
        if not st.session_state.get("scrape_running"):
            st.session_state["scrape_running"] = True
            st.session_state["scrape_started_at"] = datetime.now(timezone.utc).isoformat()
            threading.Thread(target=scrape_all, daemon=True).start()
        st.rerun()
with col_7:
    if st.button("Last 7 d"):
        st.session_state["date_start"] = today - timedelta(days=7)
        st.session_state["date_end"]   = today
with col_30:
    if st.button("Last 30 d"):
        st.session_state["date_start"] = today - timedelta(days=30)
        st.session_state["date_end"]   = today
with col_90:
    if st.button("Last 90 d"):
        st.session_state["date_start"] = today - timedelta(days=90)
        st.session_state["date_end"]   = today

# Defaults
if "date_start" not in st.session_state:
    st.session_state["date_start"] = today - timedelta(days=30)
if "date_end" not in st.session_state:
    st.session_state["date_end"] = today

# Date range picker
date_range = st.date_input(
    "Date range",
    value=(st.session_state["date_start"], st.session_state["date_end"]),
    max_value=today,
    label_visibility="collapsed",
)
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_date, end_date = date_range
    st.session_state["date_start"] = start_date
    st.session_state["date_end"]   = end_date
else:
    start_date = st.session_state["date_start"]
    end_date   = st.session_state["date_end"]

start_iso    = datetime.combine(start_date, dtime.min).replace(tzinfo=timezone.utc).isoformat()
end_iso      = datetime.combine(end_date,   dtime.max).replace(tzinfo=timezone.utc).isoformat()
window_label = f"{max((end_date - start_date).days, 1)}d"

page = st.sidebar.radio("Page", ["Portfolio Overview", "Per-Brand Drill-Down"])

# ── Scrape status banner ──────────────────────────────────────────────────────

if st.session_state.get("scrape_running"):
    started = st.session_state.get("scrape_started_at", "")
    with get_connection() as conn:
        done = conn.execute(
            "SELECT COUNT(*) FROM scrape_log WHERE run_at > ?", (started,)
        ).fetchone()[0]
    total = len(BRANDS)
    if done >= total:
        st.session_state["scrape_running"] = False
        st.success("Scrape complete — data updated.")
    else:
        st.info(f"Scraping in progress… {done}/{total} accounts done. Page will update automatically.")
        st.rerun()

all_metrics = _load_all_metrics(start_iso, end_iso)
scores      = compute_scores(all_metrics)
brand_names = list(BRANDS.keys())


# ── Page 1: Portfolio Overview ────────────────────────────────────────────────

if page == "Portfolio Overview":

    # Row 1: KPI cards
    cols = st.columns(4)
    for i, name in enumerate(brand_names):
        m      = all_metrics[name]
        state  = m["state"] or {}
        growth = m["growth"]
        with cols[i]:
            followers = state.get("followers", 0)
            d7        = growth.get("follower_delta_7d")
            d30       = growth.get("follower_delta_30d")
            d90       = growth.get("follower_delta_90d")
            d_custom, _ = get_growth_delta_for_range(BRANDS[name], start_iso, end_iso)

            st.markdown(f"**{name}**")
            st.caption(f"@{BRANDS[name]}")
            st.metric("Followers", f"{followers:,}",
                      delta=f"{d30:+,}" if d30 is not None else None)

            st.dataframe(
                pd.DataFrame({
                    "Period":        ["7 d", "30 d", "90 d", window_label],
                    "New followers": [
                        f"{d7:+,}"      if d7      is not None else "—",
                        f"{d30:+,}"     if d30     is not None else "—",
                        f"{d90:+,}"     if d90     is not None else "—",
                        f"{d_custom:+,}" if d_custom is not None else "—",
                    ],
                }),
                use_container_width=True,
                hide_index=True,
            )

            st.metric(f"Posts ({window_label})", m["posting"]["posts_count"])
            st.metric("Eng. rate", f"{m['engagement']['engagement_rate'] * 100:.2f}%")

    st.divider()

    # Row 2: Radar chart — always 3 axes, filled
    history_min = min(all_metrics[b]["growth"]["history_days"] for b in brand_names)

    axes = ["Content Velocity", "Engagement Quality", "Growth Momentum"]
    fig  = go.Figure()
    for name in brand_names:
        s    = scores[name]
        vals = [s["content_velocity"] or 0, s["engagement_quality"] or 0, s["growth_momentum"] or 0]
        color = BRAND_COLORS.get(name, "#888")
        fig.add_trace(go.Scatterpolar(
            r=vals + [vals[0]],
            theta=axes + [axes[0]],
            name=name,
            fill="toself",
            opacity=0.72,
            line=dict(color=color, width=2),
            fillcolor=color,
        ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        title="Brand Radar",
        legend=dict(orientation="h", yanchor="bottom", y=-0.25),
        margin=dict(t=60, b=60),
        paper_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)
    if history_min < 14:
        st.caption(
            f"Growth Momentum needs 14+ days of snapshot history "
            f"(currently {history_min} day{'s' if history_min != 1 else ''}) — shown as 0 until then."
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
        ("Followers",        f"{state.get('followers', '—'):,}" if state.get('followers') else "—"),
        ("Posts in window",  posting["posts_count"]),
        ("Posts / week",     f"{posting['posts_per_week']:.1f}"),
        ("Reel share",       f"{posting['reel_share'] * 100:.0f}%"),
        ("Carousel share",   f"{posting['carousel_share'] * 100:.0f}%"),
        ("Image share",      f"{posting['image_share'] * 100:.0f}%"),
        ("Avg gap (days)",   f"{posting['avg_gap_days']:.1f}" if posting["avg_gap_days"] else "—"),
        ("Avg caption len",  f"{posting['avg_caption_length']:.0f}"),
        ("Avg hashtags",     f"{posting['avg_hashtag_count']:.1f}"),
        ("Avg likes",        f"{eng['avg_likes']:.0f}"),
        ("Avg comments",     f"{eng['avg_comments']:.0f}"),
        ("Engagement rate",  f"{eng['engagement_rate'] * 100:.2f}%"),
        ("Avg video views",  f"{eng['avg_video_views']:.0f}"),
        ("Reel view rate",   f"{eng['reel_view_rate'] * 100:.2f}%"),
        ("Follower Δ 7d",    f"{growth['follower_delta_7d']:+,}"  if growth["follower_delta_7d"]  is not None else "—"),
        ("Follower Δ 30d",   f"{growth['follower_delta_30d']:+,}" if growth["follower_delta_30d"] is not None else "—"),
        ("Follower Δ 90d",   f"{growth['follower_delta_90d']:+,}" if growth["follower_delta_90d"] is not None else "—"),
        ("History (days)",   growth["history_days"]),
    ]
    st.dataframe(
        pd.DataFrame(metric_rows, columns=["Metric", "Value"]),
        use_container_width=True, hide_index=True,
    )

    st.divider()

    # Section 2: Posting heatmap
    st.subheader("Posting Heatmap")
    with get_connection() as conn:
        df_heat = pd.read_sql_query(
            "SELECT posted_at FROM posts WHERE handle = ? AND posted_at >= ? AND posted_at <= ?",
            conn, params=(handle, start_iso, end_iso),
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
            "SELECT * FROM posts WHERE handle = ? AND posted_at >= ? AND posted_at <= ?",
            conn, params=(handle, start_iso, end_iso),
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
        fig_t = px.line(
            df_trend, x="scraped_at", y="followers",
            title="Follower Count Over Time",
            color_discrete_sequence=[BRAND_COLORS.get(selected, "#833AB4")],
        )
        st.plotly_chart(fig_t, use_container_width=True)
