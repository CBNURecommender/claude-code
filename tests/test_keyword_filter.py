"""Unit tests for keyword filter module."""
import pytest

from src.filter.keyword_filter import filter_articles, matches_keywords


class TestMatchesKeywords:
    """Tests for matches_keywords function."""

    def test_empty_keywords_passes_all(self):
        matched, kws = matches_keywords("Any title", [])
        assert matched is True
        assert kws == []

    def test_single_keyword_match(self):
        matched, kws = matches_keywords("Samsung HBM4 production ramps up", ["hbm"])
        assert matched is True
        assert kws == ["hbm"]

    def test_case_insensitive(self):
        matched, kws = matches_keywords("Samsung HBM4 production", ["HBM"])
        assert matched is True
        assert kws == ["HBM"]

    def test_no_match(self):
        matched, kws = matches_keywords("Samsung HBM4 production", ["intel", "tsmc"])
        assert matched is False
        assert kws == []

    def test_multiple_matches(self):
        matched, kws = matches_keywords("TSMC and Samsung compete on HBM", ["tsmc", "hbm"])
        assert matched is True
        assert set(kws) == {"tsmc", "hbm"}

    def test_korean_substring(self):
        matched, kws = matches_keywords("삼성전자 HBM4 양산", ["삼성"])
        assert matched is True
        assert kws == ["삼성"]

    def test_partial_substring(self):
        matched, kws = matches_keywords("semiconductor industry growth", ["semi"])
        assert matched is True
        assert kws == ["semi"]


class TestFilterArticles:
    """Tests for filter_articles function."""

    def _make_articles(self, titles):
        return [{"title": t, "url": f"https://example.com/{i}"} for i, t in enumerate(titles)]

    def test_no_keywords_passes_all(self):
        articles = self._make_articles(["Article A", "Article B"])
        result = filter_articles(articles, [], [])
        assert len(result) == 2
        assert all(a["matched_keywords"] == [] for a in result)

    def test_source_keywords_filter(self):
        articles = self._make_articles(["HBM news", "Intel update", "Samsung HBM4"])
        result = filter_articles(articles, ["hbm"], [])
        assert len(result) == 2
        assert result[0]["title"] == "HBM news"
        assert result[1]["title"] == "Samsung HBM4"

    def test_global_keywords_filter(self):
        articles = self._make_articles(["HBM news", "Intel update"])
        result = filter_articles(articles, [], ["intel"])
        assert len(result) == 1
        assert result[0]["title"] == "Intel update"

    def test_source_and_global_keywords_or(self):
        """Source + global keywords combine via OR (per KWD-08)."""
        articles = self._make_articles(["HBM news", "TSMC update", "Random article"])
        result = filter_articles(articles, ["hbm"], ["tsmc"])
        assert len(result) == 2
        titles = {a["title"] for a in result}
        assert titles == {"HBM news", "TSMC update"}

    def test_matched_keywords_stored(self):
        """Matched keywords are stored in each article dict (per COL-08)."""
        articles = self._make_articles(["Samsung HBM4 report"])
        result = filter_articles(articles, ["samsung", "hbm"], [])
        assert len(result) == 1
        assert set(result[0]["matched_keywords"]) == {"samsung", "hbm"}
