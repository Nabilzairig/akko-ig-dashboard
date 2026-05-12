import sqlite3
from pathlib import Path

import config


def init_db():
    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    with open(config.SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def get_connection():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def insert_snapshot(handle, data):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO profile_snapshots
               (handle, scraped_at, followers, following, post_count, bio, is_verified)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (handle, data["scraped_at"], data["followers"], data["following"],
             data["post_count"], data["bio"], data["is_verified"]),
        )


def upsert_post(post_data):
    from datetime import datetime, timezone
    last_updated = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO posts
               (shortcode, handle, posted_at, media_type, caption, hashtag_count,
                caption_length, likes, comments, video_views, last_updated)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                post_data["shortcode"], post_data["handle"], post_data["posted_at"],
                post_data["media_type"], post_data["caption"], post_data["hashtag_count"],
                post_data["caption_length"], post_data["likes"], post_data["comments"],
                post_data["video_views"], last_updated,
            ),
        )


def log_scrape(handle, status, error_message, posts_fetched):
    from datetime import datetime, timezone
    run_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO scrape_log (handle, run_at, status, error_message, posts_fetched)
               VALUES (?, ?, ?, ?, ?)""",
            (handle, run_at, status, error_message, posts_fetched),
        )


def get_latest_snapshot(handle):
    with get_connection() as conn:
        row = conn.execute(
            """SELECT * FROM profile_snapshots WHERE handle = ?
               ORDER BY scraped_at DESC LIMIT 1""",
            (handle,),
        ).fetchone()
    return dict(row) if row else None


def get_snapshot_nearest(handle, target_iso):
    """Return the profile snapshot whose scraped_at is closest to target_iso."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT * FROM profile_snapshots
               WHERE handle = ?
               ORDER BY ABS(julianday(scraped_at) - julianday(?)) ASC
               LIMIT 1""",
            (handle, target_iso),
        ).fetchone()
    return dict(row) if row else None


def get_best_posting_slots(handle, start_iso, end_iso, top_n=3):
    """
    Return the top N (day-of-week, hour) slots ranked by average engagement
    (likes + comments) for posts in [start_iso, end_iso].
    Returns a list of dicts: {dow, hour, avg_engagement, post_count}.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                CAST(strftime('%w', posted_at) AS INTEGER) AS dow,
                CAST(strftime('%H', posted_at) AS INTEGER) AS hour,
                AVG(likes + comments)                      AS avg_engagement,
                COUNT(*)                                   AS post_count
            FROM posts
            WHERE handle = ? AND posted_at >= ? AND posted_at <= ?
            GROUP BY dow, hour
            HAVING post_count >= 1
            ORDER BY avg_engagement DESC
            LIMIT ?
            """,
            (handle, start_iso, end_iso, top_n),
        ).fetchall()
    return [dict(r) for r in rows]


def get_earliest_post_date():
    """Return the ISO timestamp of the oldest post across all handles, or None."""
    with get_connection() as conn:
        row = conn.execute("SELECT MIN(posted_at) FROM posts").fetchone()
    return row[0] if row and row[0] else None


def get_oldest_snapshot_within(handle, days):
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """SELECT * FROM profile_snapshots
               WHERE handle = ? AND scraped_at >= ?
               ORDER BY scraped_at ASC LIMIT 1""",
            (handle, cutoff),
        ).fetchone()
    return dict(row) if row else None
