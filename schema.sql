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
