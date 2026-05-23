"""Tests for Syosetsu HTML parsers."""

from pathlib import Path

import pytest

from scrapers.syosetsu import (
    SyosetsuScraper,
    _SyosetsuChapterParser,
    _SyosetsuTocParser,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def read_fixture(filename: str) -> str:
    return (FIXTURES_DIR / filename).read_text(encoding="utf-8")


class TestTocParser:
    def test_parses_title(self) -> None:
        html = read_fixture("toc_page.html")
        parser = _SyosetsuTocParser()
        parser.feed(html)
        parser.close()

        assert parser.title == "テスト小説"

    def test_parses_author(self) -> None:
        html = read_fixture("toc_page.html")
        parser = _SyosetsuTocParser()
        parser.feed(html)
        parser.close()

        assert parser.author == "テスト作者"

    def test_parses_published_date(self) -> None:
        html = read_fixture("toc_page.html")
        parser = _SyosetsuTocParser()
        parser.feed(html)
        parser.close()

        assert "".join(parser.published_date_parts) == "掲載日：2024/01/15"

    def test_parses_chapters(self) -> None:
        html = read_fixture("toc_page.html")
        parser = _SyosetsuTocParser()
        parser.feed(html)
        parser.close()

        assert len(parser.chapters) == 2
        assert parser.chapters[0] == ("第一章", "/n1234ab/1/")
        assert parser.chapters[1] == ("第二章", "/n1234ab/2/")


class TestChapterParser:
    def test_parses_chapter_title(self) -> None:
        html = read_fixture("chapter_page.html")
        parser = _SyosetsuChapterParser()
        parser.feed(html)
        parser.close()

        assert "".join(parser.title_parts) == "第一章"

    def test_parses_chapter_text(self) -> None:
        html = read_fixture("chapter_page.html")
        parser = _SyosetsuChapterParser()
        parser.feed(html)
        parser.close()

        # Includes empty paragraphs from <p><br /></p> spacing
        assert len(parser.paragraphs) == 5
        assert parser.paragraphs[0] == "これはテストの文章です。"
        assert parser.paragraphs[1] == ""
        assert parser.paragraphs[2] == "二行目のテスト文章です。"
        assert parser.paragraphs[3] == ""
        assert parser.paragraphs[4] == "三章目のテスト文章です。"

    def test_parses_published_date(self) -> None:
        html = read_fixture("chapter_page.html")
        parser = _SyosetsuChapterParser()
        parser.feed(html)
        parser.close()

        assert "".join(parser.published_date_parts) == "掲載日：2024/01/15"


class TestScraperParseToc:
    def test_extracts_toc_data(self) -> None:
        html = read_fixture("toc_page.html")
        scraper = SyosetsuScraper()
        data = scraper._parse_toc(html, "https://ncode.syosetu.com/n1234ab/")

        assert data["title"] == "テスト小説"
        assert data["author"] == "テスト作者"
        assert data["published_date"].isoformat() == "2024-01-15"
        assert len(data["chapters"]) == 2
        assert data["chapters"][0] == (
            "第一章",
            "https://ncode.syosetu.com/n1234ab/1/",
        )

    def test_single_chapter_has_empty_chapters(self) -> None:
        html = read_fixture("single_chapter.html")
        scraper = SyosetsuScraper()
        data = scraper._parse_toc(html, "https://ncode.syosetu.com/n9999cd/")

        assert data["title"] == "テスト短編"
        assert data["author"] == "短編作者"
        assert len(data["chapters"]) == 0


class TestScraperParseChapter:
    def test_extracts_chapter_data(self) -> None:
        html = read_fixture("chapter_page.html")
        scraper = SyosetsuScraper()
        chapter = scraper._parse_chapter(
            html, "第一章", "https://ncode.syosetu.com/n1234ab/1/"
        )

        assert chapter.title == "第一章"
        assert chapter.source_url == "https://ncode.syosetu.com/n1234ab/1/"
        assert "これはテストの文章です。" in chapter.text
        assert chapter.published_date.isoformat() == "2024-01-15"
