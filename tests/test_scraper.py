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
