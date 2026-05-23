"""Data models for scraped novels."""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Chapter:
    """A single chapter of a novel."""

    title: str
    text: str
    source_url: str
    published_date: Optional[date] = None


@dataclass
class Novel:
    """A complete novel with metadata and chapters."""

    title: str
    author: str
    chapters: list[Chapter] = field(default_factory=list)
    source: str = ""
    source_url: str = ""
    published_date: Optional[date] = None
