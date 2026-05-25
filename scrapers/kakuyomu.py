"""Kakuyomu scraper with TOC parsing and staggered chapter downloads."""

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

KAKUYOMU_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/147.0.0.0 Safari/537.36"
)
KAKUYOMU_BASE_URL = "https://kakuyomu.jp/"
KAKUYOMU_HOSTS = ("kakuyomu.jp",)
KAKUYOMU_PATH_PATTERN = re.compile(r"^/works/(\d+)(?:/episodes/(\d+))?/?$")
KAKUYOMU_DATE_PATTERN = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日公開")


class KakuyomuParseError(ValueError):
    """Raised when a Kakuyomu page cannot be parsed."""


class KakuyomuScraper(BaseScraper):
    """Scrape novels from Kakuyomu."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(
            headers={"User-Agent": KAKUYOMU_USER_AGENT},
            follow_redirects=True,
            timeout=30.0,
        )

    def can_handle(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.netloc.lower().replace("www.", "") in KAKUYOMU_HOSTS

    def scrape(self, url: str) -> Novel:
        base_url = self._normalize_to_base_url(url)

        # Parse TOC
        toc_html = self._fetch(base_url)
        toc_data = self._parse_toc(toc_html, base_url)

        novel = Novel(
            title=toc_data["title"],
            author=toc_data["author"],
            source="kakuyomu",
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

        for idx, (chapter_title, chapter_url, chapter_date) in enumerate(chapter_urls):
            if idx > 0:
                delay = random.uniform(30, 60)
                tqdm.write(f"Waiting {delay:.1f}s before next chapter...")
                time.sleep(delay)

            try:
                chapter_html = self._fetch(chapter_url)
                chapter = self._parse_chapter(
                    chapter_html, chapter_title, chapter_url, chapter_date
                )
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
        """Normalize any Kakuyomu URL to the novel's base URL."""
        parsed = urlparse(url)
        match = KAKUYOMU_PATH_PATTERN.match(parsed.path)
        if not match:
            raise KakuyomuParseError(f"Invalid Kakuyomu URL: {url}")

        work_id = match.group(1)
        base_path = f"/works/{work_id}"

        scheme = parsed.scheme or "https"
        netloc = parsed.netloc.lower().replace("www.", "")
        if netloc not in KAKUYOMU_HOSTS:
            netloc = KAKUYOMU_HOSTS[0]

        return f"{scheme}://{netloc}{base_path}"

    def _parse_toc(self, html: str, base_url: str) -> dict:
        parser = _KakuyomuTocParser()
        parser.feed(html)
        parser.close()

        chapters = []
        for title, href, date_text in parser.chapters:
            absolute_url = urljoin(base_url, href)
            chapters.append((title, absolute_url, date_text))

        return {
            "title": _clean_text(parser.title),
            "author": _clean_text(parser.author),
            "published_date": _parse_published_date(
                _clean_text("".join(parser.published_date_parts))
            ),
            "chapters": chapters,
        }

    def _parse_chapter(
        self,
        html: str,
        chapter_title: str,
        chapter_url: str,
        chapter_date: str | None = None,
    ) -> Chapter:
        parser = _KakuyomuChapterParser()
        parser.feed(html)
        parser.close()

        text = "\n".join(parser.paragraphs).strip("\n")
        if not text:
            raise KakuyomuParseError(f"No text found in chapter: {chapter_url}")

        # Use chapter date if available, otherwise try to parse from chapter page
        published_date = None
        if chapter_date:
            published_date = _parse_published_date(chapter_date)
        if not published_date:
            published_date = _parse_published_date(
                _clean_text("".join(parser.published_date_parts))
            )

        return Chapter(
            title=chapter_title or _clean_text("".join(parser.title_parts)),
            text=text,
            source_url=chapter_url,
            published_date=published_date,
        )


class _KakuyomuTocParser(HTMLParser):
    """Parse Kakuyomu TOC page for chapter list and metadata."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.author = ""
        self.published_date_parts: list[str] = []
        self.chapters: list[tuple[str, str, str]] = []

        self._in_title = False
        self._title_depth = 0
        self._in_author = False
        self._author_depth = 0
        self._found_author = False
        self._in_toc_link = False
        self._toc_link_depth = 0
        self._in_chapter_title = False
        self._chapter_title_depth = 0
        self._in_chapter_date = False
        self._chapter_date_depth = 0
        self._current_href = ""
        self._current_title: list[str] = []
        self._current_date: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        classes = set((attr_map.get("class") or "").split())
        href = attr_map.get("href") or ""

        if self._in_title:
            self._title_depth += 1
        if self._in_author:
            self._author_depth += 1
        if self._in_toc_link:
            self._toc_link_depth += 1
        if self._in_chapter_title:
            self._chapter_title_depth += 1
        if self._in_chapter_date:
            self._chapter_date_depth += 1

        # Title in h1
        if tag == "h1":
            self._in_title = True
            self._title_depth = 1
            return

        # Author: first <a href="/users/..."> in the page
        if (
            tag == "a"
            and href.startswith("/users/")
            and not self._found_author
        ):
            self._in_author = True
            self._author_depth = 1
            return

        # Chapter link in TOC section
        if (
            tag == "a"
            and re.match(r"/works/\d+/episodes/\d+", href)
            and not self._in_toc_link
        ):
            self._in_toc_link = True
            self._toc_link_depth = 1
            self._current_href = href
            self._current_title = []
            self._current_date = []
            return

        # Chapter title inside TOC link
        if self._in_toc_link and any(
            cls.startswith("WorkTocSection_title") for cls in classes
        ):
            self._in_chapter_title = True
            self._chapter_title_depth = 1
            return

        # Chapter date inside TOC link
        if self._in_toc_link and any(
            cls.startswith("WorkTocSection_date") for cls in classes
        ):
            self._in_chapter_date = True
            self._chapter_date_depth = 1
            return

    def handle_endtag(self, tag: str) -> None:
        if self._in_title:
            self._title_depth -= 1
            if self._title_depth <= 0:
                self._in_title = False

        if self._in_author:
            self._author_depth -= 1
            if self._author_depth <= 0:
                self._in_author = False
                self._found_author = True

        if self._in_chapter_date:
            self._chapter_date_depth -= 1
            if self._chapter_date_depth <= 0:
                self._in_chapter_date = False

        if self._in_chapter_title:
            self._chapter_title_depth -= 1
            if self._chapter_title_depth <= 0:
                self._in_chapter_title = False

        if self._in_toc_link:
            if tag == "a":
                title = "".join(self._current_title).strip()
                date_text = "".join(self._current_date).strip()
                if title and self._current_href:
                    self.chapters.append((title, self._current_href, date_text))
                self._in_toc_link = False
            else:
                self._toc_link_depth -= 1
                if self._toc_link_depth <= 0:
                    self._in_toc_link = False

    def handle_data(self, data: str) -> None:
        if self._in_chapter_title:
            self._current_title.append(data)
        elif self._in_chapter_date:
            self._current_date.append(data)
        elif self._in_title:
            self.title += data
        elif self._in_author:
            self.author += data


class _KakuyomuChapterParser(HTMLParser):
    """Parse individual Kakuyomu chapter pages."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.published_date_parts: list[str] = []
        self.paragraphs: list[str] = []

        self._in_title = False
        self._title_depth = 0
        self._in_text = False
        self._text_depth = 0
        self._paragraph_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        classes = set((attr_map.get("class") or "").split())

        if self._in_text:
            self._text_depth += 1
            if tag == "p":
                # Check if this is a blank line marker
                if "blank" in classes:
                    self._paragraph_parts = []
                else:
                    self._paragraph_parts = []
            elif tag == "br" and self._paragraph_parts is not None:
                self._paragraph_parts.append("\n")
            return

        # Chapter title: <p class="widget-episodeTitle">
        if tag == "p" and any(cls.startswith("widget-episodeTitle") for cls in classes):
            self._in_title = True
            self._title_depth = 1
            return

        # Chapter text: <div class="widget-episodeBody">
        if tag == "div" and any(cls.startswith("widget-episodeBody") for cls in classes):
            self._in_text = True
            self._text_depth = 1
            return

        if self._in_title:
            self._title_depth += 1

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

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._in_text and tag == "br" and self._paragraph_parts is not None:
            self._paragraph_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._paragraph_parts is not None:
            self._paragraph_parts.append(data)
        elif self._in_title:
            self.title_parts.append(data)


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def _parse_published_date(value: str) -> date | None:
    if not value:
        return None

    # Kakuyomu format: "2026年5月16日公開"
    match = KAKUYOMU_DATE_PATTERN.search(value)
    if match:
        year, month, day = match.groups()
        try:
            return date(int(year), int(month), int(day))
        except ValueError:
            pass

    # Fallback: try the syosetsu format
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
