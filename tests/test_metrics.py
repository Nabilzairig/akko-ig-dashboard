from datetime import datetime, timezone, timedelta
from database import insert_snapshot, upsert_post
from metrics import (
    get_current_state, get_posting_metrics,
    get_engagement_metrics, get_growth_metrics, compute_scores,
)

NOW = datetime.now(timezone.utc)


def _ts(days_ago=0):
    return (NOW - timedelta(days=days_ago)).isoformat()


def _seed_snapshot(handle, days_ago=0, followers=1000):
    insert_snapshot(handle, {
        "scraped_at": _ts(days_ago),
        "followers": followers,
        "following": 200,
        "post_count": 20,
        "bio": "",
        "is_verified": 0,
    })


def _seed_post(handle, shortcode, media_type="reel", days_ago=1,
               likes=100, comments=5, views=500):
    upsert_post({
        "shortcode": shortcode,
        "handle": handle,
        "posted_at": _ts(days_ago),
        "media_type": media_type,
        "caption": "#food #morocco",
        "hashtag_count": 2,
        "caption_length": 14,
        "likes": likes,
        "comments": comments,
        "video_views": views if media_type == "reel" else None,
    })


def test_get_current_state_returns_latest(tmp_db):
    _seed_snapshot("h1", days_ago=5, followers=800)
    _seed_snapshot("h1", days_ago=0, followers=1000)
    assert get_current_state("h1")["followers"] == 1000


def test_get_posting_metrics_empty(tmp_db):
    _seed_snapshot("h1")
    m = get_posting_metrics("h1", 30)
    assert m["posts_count"] == 0
    assert m["posts_per_week"] == 0.0


def test_get_posting_metrics_reel_share(tmp_db):
    _seed_snapshot("h1")
    _seed_post("h1", "r1", media_type="reel", days_ago=2)
    _seed_post("h1", "i1", media_type="image", days_ago=3)
    m = get_posting_metrics("h1", 30)
    assert m["posts_count"] == 2
    assert m["reel_share"] == 0.5
    assert m["image_share"] == 0.5


def test_get_engagement_metrics(tmp_db):
    _seed_snapshot("h1", followers=1000)
    _seed_post("h1", "r1", media_type="reel", likes=200, comments=10, views=500)
    m = get_engagement_metrics("h1", 30)
    assert m["avg_likes"] == 200.0
    assert m["avg_comments"] == 10.0
    assert abs(m["engagement_rate"] - 0.21) < 0.001
    assert m["avg_video_views"] == 500.0


def test_get_growth_metrics_insufficient_data(tmp_db):
    _seed_snapshot("h1", days_ago=5, followers=950)
    _seed_snapshot("h1", days_ago=0, followers=1000)
    m = get_growth_metrics("h1")
    assert m["sufficient_data_for_growth"] is False


def test_get_growth_metrics_sufficient_data(tmp_db):
    _seed_snapshot("h1", days_ago=20, followers=900)
    _seed_snapshot("h1", days_ago=0, followers=1000)
    m = get_growth_metrics("h1")
    assert m["sufficient_data_for_growth"] is True
    assert m["follower_delta_30d"] == 100


def test_compute_scores_all_equal_returns_50(tmp_db):
    brands = ["Mandi", "Fancy", "Elephant", "Add-Me"]
    all_metrics = {b: {
        "posting":    {"posts_per_week": 3.0, "reel_share": 0.6},
        "engagement": {"engagement_rate": 0.05, "reel_view_rate": 0.1},
        "growth":     {"follower_growth_pct_30d": 2.0, "follower_growth_pct_90d": 5.0,
                       "sufficient_data_for_growth": True},
    } for b in brands}
    scores = compute_scores(all_metrics)
    assert set(scores.keys()) == set(brands)
    for b in brands:
        assert scores[b]["content_velocity"] == 50


def test_compute_scores_growth_none_when_insufficient(tmp_db):
    brands = ["Mandi", "Fancy"]
    all_metrics = {b: {
        "posting":    {"posts_per_week": 5.0, "reel_share": 0.5},
        "engagement": {"engagement_rate": 0.03, "reel_view_rate": 0.0},
        "growth":     {"follower_growth_pct_30d": None, "follower_growth_pct_90d": None,
                       "sufficient_data_for_growth": False},
    } for b in brands}
    scores = compute_scores(all_metrics)
    for b in brands:
        assert scores[b]["growth_momentum"] is None
