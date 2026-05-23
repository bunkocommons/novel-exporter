"""Base scraper interface."""

from abc import ABC, abstractmethod
from models import Novel


class BaseScraper(ABC):
    """Base class for all novel scrapers."""

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Return True if this scraper can handle the given URL."""
        pass

    @abstractmethod
    def scrape(self, url: str) -> Novel:
        """Scrape the novel and return a Novel instance."""
        pass
