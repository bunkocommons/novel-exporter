"""Base exporter interface."""

from abc import ABC, abstractmethod

from models import Novel


class BaseExporter(ABC):
    """Base class for all novel exporters."""

    @abstractmethod
    def export(self, novel: Novel, filepath: str) -> None:
        """Export the novel to the given file path."""
        pass
