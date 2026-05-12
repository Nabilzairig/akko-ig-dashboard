# AKKO Instagram Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Streamlit dashboard that scrapes 4 public AKKO Instagram accounts daily, stores snapshots in SQLite, and displays head-to-head benchmark scores and rule-based recommendations.

**Architecture:** Layered pipeline — config constants → SQLite schema → database CRUD → instaloader scraper → pandas metrics → rule engine → Streamlit UI with APScheduler. Each layer is a focused module with a clean interface; later layers only import from earlier ones.

**Tech Stack:** Python 3.11+, instaloader, sqlite3, pandas, streamlit, plotly, apscheduler, pytz, pytest

---

## File Map

| File | Role |
|------|------|
| `config.py` | Constants: brand handles, paths, timing |
| `schema.sql` | SQLite DDL — 3 tables + indexes |
| `database.py` | DB init and all CRUD functions |
| `scraper.py` | instaloader scraping with rate-limit handling |
| `metrics.py` | Posting, engagement, growth analytics + score normalization |
| `recommendations.py` | Rule engine → list of recommendation strings |
| `dashboard.py` | Streamlit UI (2 pages) + APScheduler |
| `requirements.txt` | Pinned dependencies |
| `README.md` | Setup and usage guide |
| `tests/__init__.py` | Empty — marks tests as a package |
| `tests/conftest.py` | pytest fixtures (temp DB via monkeypatch) |
| `tests/test_database.py` | Unit tests for database.py |
| `tests/test_scraper.py` | Unit tests for scraper.py (mocked instaloader) |
| `tests/test_metrics.py` | Unit tests for metrics.py |
| `tests/test_recommendations.py` | Unit tests for recommendations.py |

---

### Task 1: config.py + requirements.txt

**Files:**
- Create: `config.py`
- Create: `requirements.txt`

- [ ] **Step 1: Create config.py**

```python
from pathlib import Path

BASE_DIR = Path(__file__).parent

BRANDS = {
    "Mandi":    "mandi.basmati.morocco",
    "Fancy":    "fancy.morocco",
    "Elephant": "elephant_morocco",
    "Add-Me":   "addme.morocco",
}

TIMEZONE = "Africa/Casablanca"
SCRAPE_HOUR = 4
POSTS_PER_SCRAPE = 12
SLEEP_BETWEEN_POSTS = 8
SLEEP_BETWEEN_PROFILES = 75

DB_PATH = str(BASE_DIR / "data" / "akko.db")
SCHEMA_PATH = str(BASE_DIR / "schema.sql")
```

- [ ] **Step 2: Create requirements.txt**

```
instaloader>=4.13
streamlit>=1.36
pandas>=2.2
plotly>=5.22
apscheduler>=3.10
pytz>=2024.1
pytest>=8.0
```

- [ ] **Step 3: Install dependencies**

```bash
cd "/Users/bilrig/Documents/CODE/AKKO IG DASH"
pip install -r requirements.txt
```

Expected: All packages install without errors.

- [ ] **Step 4: Smoke-test config import**

```bash
python -c "from config import BRANDS; print(list(BRANDS.keys()))"
```

Expected:
```
['Mandi', 'Fancy', 'Elephant', 'Add-Me']
```

---

### Task 2: schema.sql

**Files:**
- Create: `schema.sql`

- [ ] **Step 1: Create schema.sql**

```sql
CREATE TABLE IF NOT EXISTS profile_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    handle      TEXT      NOT NULL,
    scraped_at  TIMESTAMP NOT NULL,
    followers   INTEGER,
    following   INTEGER,
    post_count  INTEGER,
    bio         TEXT,
    is_verified INTEGER
);

CREATE TABLE IF NOT EXISTS posts (
    shortcode      TEXT PRIMARY KEY,
    handle         TEXT      NOT NULL,
    posted_at      TIMESTAMP NOT NULL,
    media_type     TEXT      NOT NULL,
    caption        TEXT,
    hashtag_count  INTEGER,
    caption_length INTEGER,
    likes          INTEGER,
    comments       INTEGER,
    video_views    INTEGER,
    last_updated   TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS scrape_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    handle        TEXT      NOT NULL,
    run_at        TIMESTAMP NOT NULL,
    status        TEXT      NOT NULL,
    error_message TEXT,
    posts_fetched INTEGER
);

CREATE INDEX IF NOT EXISTS idx_posts_handle         ON posts(handle);
CREATE INDEX IF NOT EXISTS idx_posts_posted_at      ON posts(posted_at);
CREATE INDEX IF NOT EXISTS idx_snapshots_handle     ON profile_snapshots(handle);
CREATE INDEX IF NOT EXISTS idx_snapshots_scraped_at ON profile_snapshots(scraped_at);
CREATE INDEX IF NOT EXISTS idx_scrape_log_run_at    ON scrape_log(run_at);
```

- [ ] **Step 2: Smoke-test schema syntax**

```bash
python -c "import sqlite3; conn = sqlite3.connect(':memory:'); conn.executescript(open('schema.sql').read()); print('schema OK')"
```

Expected: `schema OK`

---

### Task 3: database.py + tests

**Files:**
- Create: `database.py`
- Create: `tests/__init__.py` (empty file)
- Create: `tests/conftest.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: Write failing tests**

Create `tests/__init__.py` — empty file.

Create `tests/conftest.py`:

```python
import pytest
import config
from database import init_db

@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
    init_db()
```

Create `tests/test_database.py`:

```python
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
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd "/Users/bilrig/Documents/CODE/AKKO IG DASH"
pytest tests/test_database.py -v
```

Expected: `ModuleNotFoundError: No module named 'database'`

- [ ] **Step 3: Create database.py**

```python
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
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_database.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add config.py schema.sql requirements.txt database.py tests/__init__.py tests/conftest.py tests/test_database.py
git commit -m "feat: add config, schema, and database layer with tests"
```

---

### Task 4: scraper.py + tests

**Files:**
- Create: `scraper.py`
- Create: `tests/test_scraper.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_scraper.py`:

```python
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


def _make_post(shortcode="sc1", typename="GraphImage", is_video=False,
               likes=50, comments=3, views=None, caption="Hello #world"):
    post = MagicMock()
    post.shortcode = shortcode
    post.typename = typename
    post.is_video = is_video
    post.likes = likes
    post.comments = comments
    post.video_view_count = views
    post.caption = caption
    post.date_utc = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return post


def _make_profile(followers=5000, followees=100, mediacount=30,
                  biography="Bio", is_verified=False, posts=None):
    profile = MagicMock()
    profile.followers = followers
    profile.followees = followees
    profile.mediacount = mediacount
    profile.biography = biography
    profile.is_verified = is_verified
    profile.get_posts.return_value = iter(posts or [])
    return profile


def test_media_type_image():
    from scraper import _media_type
    assert _media_type(_make_post(typename="GraphImage")) == "image"


def test_media_type_carousel():
    from scraper import _media_type
    assert _media_type(_make_post(typename="GraphSidecar")) == "carousel"


def test_media_type_reel():
    from scraper import _media_type
    assert _media_type(_make_post(typename="GraphVideo")) == "reel"


def test_scrape_profile_success(tmp_db):
    from scraper import scrape_profile
    mock_profile = _make_profile(posts=[_make_post()])
    with patch("scraper.instaloader.Instaloader") as MockLoader, \
         patch("scraper.instaloader.Profile.from_username", return_value=mock_profile), \
         patch("scraper.time.sleep"):
        MockLoader.return_value = MagicMock()
        result = scrape_profile("test_handle")
    assert result["status"] == "success"
    assert result["posts_fetched"] == 1


def test_scrape_profile_rate_limited(tmp_db):
    from scraper import scrape_profile
    import instaloader.exceptions
    with patch("scraper.instaloader.Instaloader"), \
         patch("scraper.instaloader.Profile.from_username",
               side_effect=instaloader.exceptions.TooManyRequestsException("rl")):
        result = scrape_profile("test_handle")
    assert result["status"] == "rate_limited"
    assert result["posts_fetched"] == 0


def test_scrape_profile_generic_error(tmp_db):
    from scraper import scrape_profile
    with patch("scraper.instaloader.Instaloader"), \
         patch("scraper.instaloader.Profile.from_username",
               side_effect=Exception("unexpected")):
        result = scrape_profile("test_handle")
    assert result["status"] == "error"
    assert result["posts_fetched"] == 0
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_scraper.py -v
```

Expected: `ModuleNotFoundError: No module named 'scraper'`

- [ ] **Step 3: Create scraper.py**

```python
import re
import time
from datetime import datetime, timezone

import instaloader

from config import BRANDS, POSTS_PER_SCRAPE, SLEEP_BETWEEN_POSTS, SLEEP_BETWEEN_PROFILES
from database import init_db, insert_snapshot, upsert_post, log_scrape

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def _media_type(post):
    t = post.typename
    if t == "GraphSidecar":
        return "carousel"
    if t == "GraphVideo":
        return "reel"
    return "image"


def scrape_profile(handle):
    """Scrape the latest POSTS_PER_SCRAPE posts from a public profile and persist to DB."""
    loader = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        save_metadata=False,
        post_metadata_txt_pattern="",
    )
    loader.context._session.headers["User-Agent"] = _UA

    try:
        profile = instaloader.Profile.from_username(loader.context, handle)
        scraped_at = datetime.now(timezone.utc).isoformat()

        insert_snapshot(handle, {
            "scraped_at": scraped_at,
            "followers": profile.followers,
            "following": profile.followees,
            "post_count": profile.mediacount,
            "bio": profile.biography,
            "is_verified": int(profile.is_verified),
        })

        posts_fetched = 0
        for post in profile.get_posts():
            if posts_fetched >= POSTS_PER_SCRAPE:
                break
            caption = post.caption or ""
            upsert_post({
                "shortcode": post.shortcode,
                "handle": handle,
                "posted_at": post.date_utc.isoformat(),
                "media_type": _media_type(post),
                "caption": caption,
                "hashtag_count": len(re.findall(r"#\w+", caption)),
                "caption_length": len(caption),
                "likes": post.likes,
                "comments": post.comments,
                "video_views": post.video_view_count if post.is_video else None,
            })
            posts_fetched += 1
            time.sleep(SLEEP_BETWEEN_POSTS)

        log_scrape(handle, "success", None, posts_fetched)
        return {"status": "success", "posts_fetched": posts_fetched}

    except (
        instaloader.exceptions.TooManyRequestsException,
        instaloader.exceptions.QueryReturnedBadRequestException,
    ):
        log_scrape(handle, "rate_limited", "Rate limit hit", 0)
        return {"status": "rate_limited", "posts_fetched": 0}

    except Exception as exc:
        log_scrape(handle, "error", str(exc), 0)
        return {"status": "error", "posts_fetched": 0}


def scrape_all():
    """Scrape all brands sequentially with inter-profile delays. Returns status dict."""
    handles = list(BRANDS.values())
    results = {}
    for i, handle in enumerate(handles):
        results[handle] = scrape_profile(handle)
        if i < len(handles) - 1:
            time.sleep(SLEEP_BETWEEN_PROFILES)
    return results


if __name__ == "__main__":
    init_db()
    scrape_all()
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_scraper.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: add scraper with rate-limit handling and mock tests"
```

---

### Task 5: metrics.py + tests

**Files:**
- Create: `metrics.py`
- Create: `tests/test_metrics.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_metrics.py`:

```python
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
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_metrics.py -v
```

Expected: `ModuleNotFoundError: No module named 'metrics'`

- [ ] **Step 3: Create metrics.py**

```python
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
    history_days     = (datetime.now(timezone.utc) - first_dt).days
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
    """Min-max normalize; returns 50 for all when min == max."""
    filtered = [v for v in values if v is not None]
    if not filtered:
        return [50] * len(values)
    mn, mx = min(filtered), max(filtered)
    if mn == mx:
        return [50 if v is not None else None for v in values]
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
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_metrics.py -v
```

Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add metrics.py tests/test_metrics.py
git commit -m "feat: add metrics layer with score normalization and tests"
```

---

### Task 6: recommendations.py + tests

**Files:**
- Create: `recommendations.py`
- Create: `tests/test_recommendations.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_recommendations.py`:

```python
from recommendations import generate_recommendations


def _bundle(posts_per_week=3.0, reel_share=0.6, avg_gap_days=2.0,
            engagement_rate=0.05, reel_view_rate=0.1,
            sufficient=True, follower_growth_pct_30d=3.0):
    return {
        "posting":    {"posts_per_week": posts_per_week, "reel_share": reel_share,
                       "avg_gap_days": avg_gap_days},
        "engagement": {"engagement_rate": engagement_rate, "reel_view_rate": reel_view_rate},
        "growth":     {"sufficient_data_for_growth": sufficient,
                       "follower_growth_pct_30d": follower_growth_pct_30d},
    }


def _scores(cv=50, eq=50, gm=50):
    return {"content_velocity": cv, "engagement_quality": eq, "growth_momentum": gm}


def test_rule1_volume_up_quality_down():
    recs = generate_recommendations("Mandi", _bundle(), _scores(cv=70, eq=30))
    assert any("Audit creative direction" in r for r in recs)


def test_rule2_underpublished():
    recs = generate_recommendations("Mandi", _bundle(), _scores(cv=30, eq=70))
    assert any("Underpublished" in r for r in recs)


def test_rule3_reel_ratio_low():
    recs = generate_recommendations("Mandi", _bundle(reel_share=0.3), _scores())
    assert any("Reel ratio" in r for r in recs)
    assert any("30%" in r for r in recs)


def test_rule4_posting_gap():
    recs = generate_recommendations("Mandi", _bundle(avg_gap_days=6.0), _scores())
    assert any("Posting gap" in r for r in recs)
    assert any("6.0" in r for r in recs)


def test_rule5_audience_saturated():
    recs = generate_recommendations("Mandi", _bundle(sufficient=True),
                                    _scores(gm=20, eq=60))
    assert any("Audience saturated" in r for r in recs)


def test_rule6_on_track_when_no_rules_fire():
    recs = generate_recommendations("Mandi",
                                    _bundle(reel_share=0.6, avg_gap_days=2.0),
                                    _scores(cv=50, eq=50, gm=50))
    assert recs == ["On track. No corrective action required."]


def test_multiple_rules_can_fire():
    recs = generate_recommendations("Mandi",
                                    _bundle(reel_share=0.3, avg_gap_days=6.0),
                                    _scores(cv=70, eq=30))
    assert len(recs) >= 2
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_recommendations.py -v
```

Expected: `ModuleNotFoundError: No module named 'recommendations'`

- [ ] **Step 3: Create recommendations.py**

```python
def generate_recommendations(brand_name, metrics_bundle, scores):
    """Evaluate ordered rule set and return all triggered recommendation strings."""
    eq = scores.get("engagement_quality") or 50
    cv = scores.get("content_velocity")   or 50
    gm = scores.get("growth_momentum")

    posting  = metrics_bundle["posting"]
    growth   = metrics_bundle["growth"]

    reel_share   = posting["reel_share"]
    avg_gap_days = posting["avg_gap_days"]
    sufficient   = growth["sufficient_data_for_growth"]

    triggered = []

    if eq < 40 and cv > 60:
        triggered.append(
            "Volume up, quality down. Audit creative direction before publishing more."
        )

    if eq > 60 and cv < 40:
        triggered.append(
            "Underpublished. Strong creative wasted. Increase posting frequency."
        )

    if reel_share < 0.50:
        triggered.append(
            f"Reel ratio at {reel_share * 100:.0f}%. Format underweighted. Shift mix toward reels."
        )

    if avg_gap_days is not None and avg_gap_days > 4:
        triggered.append(
            f"Posting gap averaging {avg_gap_days:.1f} days. Cadence inconsistent. Tighten schedule."
        )

    if gm is not None and gm < 30 and eq > 50 and sufficient:
        triggered.append(
            "Audience saturated. Engagement healthy but follower growth stalled. "
            "Run acquisition push via Meta Ads."
        )

    if not triggered:
        triggered.append("On track. No corrective action required.")

    return triggered
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_recommendations.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: All 20 tests PASS across all four test files.

- [ ] **Step 6: Commit**

```bash
git add recommendations.py tests/test_recommendations.py
git commit -m "feat: add rule-based recommendations with tests"
```

---

### Task 7: dashboard.py

**Files:**
- Create: `dashboard.py`

Note: Streamlit UI cannot be unit-tested. Verify manually by launching.

- [ ] **Step 1: Create dashboard.py**

```python
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
        df_scores.style.applymap(_score_color, subset=score_cols),
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
```

- [ ] **Step 2: Verify app launches**

```bash
cd "/Users/bilrig/Documents/CODE/AKKO IG DASH"
streamlit run dashboard.py
```

Expected: Browser opens at `http://localhost:8501`. Both pages render without Python errors. KPI cards show zeros (no data yet). Force refresh button visible.

- [ ] **Step 3: Commit**

```bash
git add dashboard.py
git commit -m "feat: add Streamlit dashboard with two pages and APScheduler"
```

---

### Task 8: README.md + final verification

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create README.md**

```markdown
# AKKO Portfolio Instagram Benchmark

Local Streamlit dashboard that scrapes 4 public AKKO brand Instagram accounts daily via `instaloader`, stores post and follower data in SQLite, and produces head-to-head benchmark scores (Content Velocity, Engagement Quality, Growth Momentum) with rule-based recommendations. No API tokens, no login, no external services.

## Install

```bash
pip install -r requirements.txt
```

## Seed the database

```bash
python scraper.py
```

## Launch the dashboard

```bash
streamlit run dashboard.py
```

## Daily refresh

When the Streamlit app is running, `apscheduler` triggers a scrape automatically at 04:00 Africa/Casablanca time.

For OS-level cron (when the app is not running), add to crontab (`crontab -e`):

```
0 4 * * * cd /path/to/akko-ig-dash && python scraper.py >> logs/cron.log 2>&1
```

## Notes

- **Rate limits**: if scrapes fail with `TooManyRequestsException`, pause for 24 hours and consider switching to every-other-day scraping.
- **Growth Momentum score**: requires 14+ days of accumulated daily snapshots. The radar chart shows 2 axes until that threshold is reached.
- **Out of scope by design**: reach, impressions, saves, shares, story metrics, audience demographics. These require the Meta Graph API. Export from Meta Business Suite manually if needed.
```

- [ ] **Step 2: Run full test suite**

```bash
cd "/Users/bilrig/Documents/CODE/AKKO IG DASH"
pytest -v
```

Expected: All tests PASS.

- [ ] **Step 3: Verify project file structure**

```bash
ls -1
```

Expected output includes: `config.py`, `schema.sql`, `database.py`, `scraper.py`, `metrics.py`, `recommendations.py`, `dashboard.py`, `requirements.txt`, `README.md`, `tests/`

- [ ] **Step 4: Final commit**

```bash
git add README.md
git commit -m "feat: complete AKKO Instagram dashboard — all modules, tests, and docs"
```
