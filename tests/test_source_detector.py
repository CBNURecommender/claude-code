"""Unit tests for source type auto-detector."""
import pytest

from src.collector.source_detector import detect_source_type, _RSS_URL_PATTERNS


class TestRSSURLPatterns:
    """Tests for URL pattern matching (no network needed)."""

    def test_xml_extension(self):
        assert _RSS_URL_PATTERNS.search("https://www.tomshardware.com/feeds.xml")

    def test_feed_path(self):
        assert _RSS_URL_PATTERNS.search("https://wccftech.com/feed/")

    def test_rss_path(self):
        assert _RSS_URL_PATTERNS.search("https://example.com/rss")

    def test_atom_path(self):
        assert _RSS_URL_PATTERNS.search("https://example.com/atom")

    def test_html_no_match(self):
        assert not _RSS_URL_PATTERNS.search("https://example.com/news/page.html")

    def test_plain_url_no_match(self):
        assert not _RSS_URL_PATTERNS.search("https://www.etnews.com/news/section")


class TestDetectSourceType:
    """Tests for the async detect_source_type function."""

    @pytest.mark.asyncio
    async def test_xml_url_returns_rss(self):
        result = await detect_source_type("https://www.tomshardware.com/feeds.xml")
        assert result == "rss"

    @pytest.mark.asyncio
    async def test_feed_url_returns_rss(self):
        result = await detect_source_type("https://wccftech.com/feed/")
        assert result == "rss"

    @pytest.mark.asyncio
    async def test_rss_url_returns_rss(self):
        result = await detect_source_type("https://example.com/rss")
        assert result == "rss"

    @pytest.mark.asyncio
    async def test_atom_url_returns_rss(self):
        result = await detect_source_type("https://example.com/atom")
        assert result == "rss"

    @pytest.mark.asyncio
    async def test_html_url_returns_html(self):
        # This URL has no RSS patterns; HEAD request will fail -> fallback to html
        result = await detect_source_type("https://invalid.nonexistent.test/page", timeout=1.0)
        assert result == "html"

    @pytest.mark.asyncio
    async def test_network_error_fallback_to_html(self):
        result = await detect_source_type("https://this-does-not-exist.invalid/", timeout=1.0)
        assert result == "html"
