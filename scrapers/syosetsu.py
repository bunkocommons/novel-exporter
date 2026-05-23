"""Syosetsu scraper with TOC parsing and staggered chapter downloads."""

import random
import re
import time
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx
from tqdm import tqdm

from models import Chapter, Novel
from scrapers.base import BaseScraper

SYOSETSU_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/147.0.0.0 Safari/537.36"
)
SYOSETSU_BASE_URL = "https://ncode.syosetu.com/"
SYOSETSU_HOSTS = ("ncode.syosetu.com", "novel18.syosetu.com")
WRITER_ID_PATTERN = re.compile(r"mypage\.syosetu\.com/(\d+)/?")
SYOSETSU_PATH_PATTERN = re.compile(r"^/([a-z]\d+[a-z]+)(?:/(\d+))?/?$", re.I)


class SyosetsuParseError(ValueError):
    """Raised when a Syosetsu page cannot be parsed."""


class SyosetsuScraper(BaseScraper):
    """Scrape novels from Syosetsu."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(
            headers={"User-Agent": SYOSETSU_USER_AGENT},
            follow_redirects=True,
            timeout=30.0,
        )

    def can_handle(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.netloc.lower().replace("www.", "") in SYOSETSU_HOSTS

    def scrape(self, url: str) -> Novel:
        base_url = self._normalize_to_base_url(url)

        # Parse TOC
        toc_html = self._fetch(base_url)
        toc_data = self._parse_toc(toc_html, base_url)

        novel = Novel(
            title=toc_data["title"],
            author=toc_data["author"],
            source="syosetsu",
            source_url=base_url,
            published_date=toc_data.get("published_date"),
        )

        chapter_urls = toc_data["chapters"]

        # If no chapter list found, the base URL is a single-chapter story
        if not chapter_urls:
            tqdm.write("Single-chapter story detected, parsing base page...")
            chapter = self._parse_chapter(toc_html, toc_data["title"], base_url)
            novel.chapters.append(chapter)
            return novel

        # Download chapters with progress bar and staggered delays
        progress = tqdm(
            total=len(chapter_urls),
            desc="Downloading chapters",
            unit="ch",
        )

        for idx, (chapter_title, chapter_url) in enumerate(chapter_urls):
            if idx > 0:
                delay = random.uniform(30, 60)
                tqdm.write(f"Waiting {delay:.1f}s before next chapter...")
                time.sleep(delay)

            try:
                chapter_html = self._fetch(chapter_url)
                chapter = self._parse_chapter(chapter_html, chapter_title, chapter_url)
                novel.chapters.append(chapter)
                progress.update(1)
            except Exception as e:
                tqdm.write(f"Error downloading {chapter_url}: {e}")
                raise

        progress.close()
        return novel

    def _fetch(self, url: str, retries: int = 3) -> str:
        for attempt in range(retries):
            try:
                response = self.client.get(url)
                response.raise_for_status()
                return response.text
            except Exception:
                if attempt < retries - 1:
                    time.sleep(2**attempt)
                else:
                    raise
        raise RuntimeError("Unreachable")

    def _normalize_to_base_url(self, url: str) -> str:
        """Normalize any Syosetsu URL to the novel's base URL."""
        parsed = urlparse(url)
        match = SYOSETSU_PATH_PATTERN.match(parsed.path)
        if not match:
            raise SyosetsuParseError(f"Invalid Syosetsu URL: {url}")

        ncode = match.group(1).lower()
        base_path = f"/{ncode}/"

        scheme = parsed.scheme or "https"
        netloc = parsed.netloc.lower().replace("www.", "")
        if netloc not in SYOSETSU_HOSTS:
            netloc = SYOSETSU_HOSTS[0]

        return f"{scheme}://{netloc}{base_path}"

    def _parse_toc(self, html: str, base_url: str) -> dict:
        parser = _SyosetsuTocParser()
        parser.feed(html)
        parser.close()

        chapters = []
        for title, href in parser.chapters:
            absolute_url = urljoin(base_url, href)
            chapters.append((title, absolute_url))

        return {
            "title": _clean_text(parser.title),
            "author": _clean_text(parser.author),
            "published_date": _parse_published_date(
                _clean_text("".join(parser.published_date_parts))
            ),
            "chapters": chapters,
        }

    def _parse_chapter(
        self, html: str, chapter_title: str, chapter_url: str
    ) -> Chapter:
        parser = _SyosetsuChapterParser()
        parser.feed(html)
        parser.close()

        text = "\n".join(parser.paragraphs).strip("\n")
        if not text:
            raise SyosetsuParseError(f"No text found in chapter: {chapter_url}")

        return Chapter(
            title=chapter_title or _clean_text("".join(parser.title_parts)),
            text=text,
            source_url=chapter_url,
            published_date=_parse_published_date(
                _clean_text("".join(parser.published_date_parts))
            ),
        )


class _SyosetsuTocParser(HTMLParser):
    """Parse Syosetsu TOC page for chapter list and metadata."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.author = ""
        self.published_date_parts: list[str] = []
        self.chapters: list[tuple[str, str]] = []

        self._in_title = False
        self._title_depth = 0
        self._in_author = False
        self._author_depth = 0
        self._in_author_link = False
        self._in_published_date = False
        self._published_date_depth = 0
        self._in_chapter_link = False
        self._current_chapter_title: list[str] = []
        self._current_href = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        classes = set((attr_map.get("class") or "").split())

        if self._in_title:
            self._title_depth += 1
        if self._in_author:
            self._author_depth += 1
        if self._in_published_date:
            self._published_date_depth += 1

        if tag == "h1" and "p-novel__title" in classes:
            self._in_title = True
            self._title_depth = 1
            return

        if tag == "div" and "p-novel__author" in classes:
            self._in_author = True
            self._author_depth = 1
            return

        if tag == "div" and "p-novel__date-published" in classes:
            self._in_published_date = True
            self._published_date_depth = 1
            return

        if self._in_author and tag == "a":
            self._in_author_link = True
            return

        if tag == "a" and "p-eplist__subtitle" in classes:
            self._in_chapter_link = True
            self._current_href = attr_map.get("href") or ""
            self._current_chapter_title = []
            return

    def handle_endtag(self, tag: str) -> None:
        if self._in_title:
            self._title_depth -= 1
            if self._title_depth <= 0:
                self._in_title = False

        if self._in_author:
            if tag == "a":
                self._in_author_link = False
            self._author_depth -= 1
            if self._author_depth <= 0:
                self._in_author = False

        if self._in_published_date:
            self._published_date_depth -= 1
            if self._published_date_depth <= 0:
                self._in_published_date = False

        if tag == "a" and self._in_chapter_link:
            title = "".join(self._current_chapter_title).strip()
            if title and self._current_href:
                self.chapters.append((title, self._current_href))
            self._in_chapter_link = False

    def handle_data(self, data: str) -> None:
        if self._in_chapter_link:
            self._current_chapter_title.append(data)
        elif self._in_title:
            self.title += data
        elif self._in_author_link:
            self.author += data
        elif self._in_published_date:
            self.published_date_parts.append(data)


class _SyosetsuChapterParser(HTMLParser):
    """Parse individual Syosetsu chapter pages."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.published_date_parts: list[str] = []
        self.paragraphs: list[str] = []

        self._in_title = False
        self._title_depth = 0
        self._in_published_date = False
        self._published_date_depth = 0
        self._in_text = False
        self._text_depth = 0
        self._paragraph_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        classes = set((attr_map.get("class") or "").split())

        if self._in_text:
            self._text_depth += 1
            if tag == "p":
                self._paragraph_parts = []
            elif tag == "br" and self._paragraph_parts is not None:
                self._paragraph_parts.append("\n")
            return

        if tag == "h1" and "p-novel__title" in classes:
            self._in_title = True
            self._title_depth = 1
            return

        if tag == "div" and "p-novel__date" in classes:
            # Try both old and new class names
            pass

        if tag == "div" and "p-novel__date-published" in classes:
            self._in_published_date = True
            self._published_date_depth = 1
            return

        if tag == "div" and "js-novel-text" in classes:
            self._in_text = True
            self._text_depth = 1
            return

        if self._in_title:
            self._title_depth += 1
        if self._in_published_date:
            self._published_date_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._in_text:
            if tag == "p" and self._paragraph_parts is not None:
                paragraph = "".join(self._paragraph_parts).strip("\n")
                self.paragraphs.append(paragraph)
                self._paragraph_parts = None

            self._text_depth -= 1
            if self._text_depth <= 0:
                self._in_text = False
            return

        if self._in_title:
            self._title_depth -= 1
            if self._title_depth <= 0:
                self._in_title = False

        if self._in_published_date:
            self._published_date_depth -= 1
            if self._published_date_depth <= 0:
                self._in_published_date = False

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._in_text and tag == "br" and self._paragraph_parts is not None:
            self._paragraph_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._paragraph_parts is not None:
            self._paragraph_parts.append(data)
        elif self._in_title:
            self.title_parts.append(data)
        elif self._in_published_date:
            self.published_date_parts.append(data)


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def _parse_published_date(value: str) -> date | None:
    if not value:
        return None

    _, _, date_part = value.partition("：")
    date_part = date_part or value
    date_part = (
        date_part.replace("年", "-").replace("月", "-").replace("日", "").strip("-")
    )

    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_part, fmt).date()
        except ValueError:
            continue

    try:
        return date.fromisoformat(date_part.replace("/", "-"))
    except ValueError:
        return None
