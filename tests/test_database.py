from datetime import datetime, timezone, timedelta
from database import (
    insert_snapshot, upsert_post, log_scrape,
    get_latest_snapshot, get_oldest_snapshot_within, get_connection,
)

NOW = datetime.now(timezone.utc).isoformat()

SNAPSHOT = {
    "scraped_at": NOW,
    "followers": 1000,
    "following": 200,
    "post_count": 50,
    "bio": "Test bio",
    "is_verified": 0,
}

POST = {
    "shortcode": "abc123",
    "handle": "test_handle",
    "posted_at": NOW,
    "media_type": "image",
    "caption": "Test #caption",
    "hashtag_count": 1,
    "caption_length": 13,
    "likes": 100,
    "comments": 5,
    "video_views": None,
}


def test_insert_and_retrieve_snapshot(tmp_db):
    insert_snapshot("test_handle", SNAPSHOT)
    row = get_latest_snapshot("test_handle")
    assert row is not None
    assert row["followers"] == 1000
    assert row["handle"] == "test_handle"


def test_upsert_post_inserts(tmp_db):
    upsert_post(POST)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM posts WHERE shortcode = ?", ("abc123",)
        ).fetchone()
    assert row is not None
    assert row["likes"] == 100


def test_upsert_post_updates_on_duplicate(tmp_db):
    upsert_post(POST)
    upsert_post({**POST, "likes": 999})
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM posts WHERE shortcode = ?", ("abc123",)
        ).fetchone()
    assert row["likes"] == 999


def test_log_scrape_writes_row(tmp_db):
    log_scrape("test_handle", "success", None, 5)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM scrape_log WHERE handle = ?", ("test_handle",)
        ).fetchone()
    assert row["status"] == "success"
    assert row["posts_fetched"] == 5


def test_get_latest_snapshot_returns_most_recent(tmp_db):
    old = {**SNAPSHOT,
           "scraped_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
           "followers": 800}
    insert_snapshot("test_handle", old)
    insert_snapshot("test_handle", SNAPSHOT)
    row = get_latest_snapshot("test_handle")
    assert row["followers"] == 1000


def test_get_oldest_snapshot_within(tmp_db):
    old = {**SNAPSHOT,
           "scraped_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
           "followers": 700}
    insert_snapshot("test_handle", old)
    insert_snapshot("test_handle", SNAPSHOT)
    row = get_oldest_snapshot_within("test_handle", 30)
    assert row["followers"] == 700


def test_get_latest_snapshot_returns_none_when_empty(tmp_db):
    assert get_latest_snapshot("nonexistent") is None
