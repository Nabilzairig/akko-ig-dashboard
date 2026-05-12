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
