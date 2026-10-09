"""Module 1 tests (offline)."""
import pytest

from ingest import ocr, router


@pytest.mark.parametrize("url,name,support", [
    ("https://www.youtube.com/watch?v=abc", "youtube", "supported"),
    ("https://youtu.be/abc", "youtube", "supported"),
    ("https://x.com/user/status/123", "x", "supported"),
    ("https://twitter.com/user/status/123", "x", "supported"),
    ("https://www.instagram.com/reel/xyz/", "instagram", "unsupported"),
    ("https://www.reddit.com/r/india/comments/abc/", "reddit", "partial"),
    ("https://www.facebook.com/watch/?v=1", "facebook", "partial"),
    ("https://example.com/pic.JPG", "image", "supported"),
    ("https://example.com/news/article-1", "web", "supported"),
])
def test_detect(url, name, support):
    info = router.detect(url)
    assert info.name == name and info.support == support


def test_detect_rejects_non_http():
    with pytest.raises(ValueError):
        router.detect("ftp://x.com/file")
    with pytest.raises(ValueError):
        router.detect("not a url")


def test_tweet_id():
    assert router.tweet_id("https://x.com/a/status/1234567890?s=20") == "1234567890"
    assert router.tweet_id("https://x.com/a") is None


def test_dedupe_lines_ignores_case_and_punctuation():
    assert ocr.dedupe_lines(["Breaking News!", "breaking news", "GDP 8%", "GDP 8 %"]) == ["Breaking News!", "GDP 8%"]


def test_unsupported_platform_raises():
    from ingest import extract
    with pytest.raises(extract.UnsupportedPlatform):
        extract.fetch("https://www.instagram.com/p/abc/", "t1")
