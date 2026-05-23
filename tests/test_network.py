"""Tests for network retry logic."""

import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from scrapers.syosetsu import SyosetsuScraper, SyosetsuParseError


class TestFetchRetry:
    def test_succeeds_on_first_attempt(self) -> None:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "<html>ok</html>"
        mock_client.get.return_value = mock_response

        scraper = SyosetsuScraper(client=mock_client)
        result = scraper._fetch("https://example.com/test")

        assert result == "<html>ok</html>"
        assert mock_client.get.call_count == 1

    def test_retries_on_500_error_then_succeeds(self) -> None:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "<html>ok</html>"

        # First call raises 500, second call succeeds
        mock_client.get.side_effect = [
            httpx.HTTPStatusError(
                "Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            ),
            mock_response,
        ]

        scraper = SyosetsuScraper(client=mock_client)
        result = scraper._fetch("https://example.com/test")

        assert result == "<html>ok</html>"
        assert mock_client.get.call_count == 2

    def test_retries_up_to_three_times_then_raises(self) -> None:
        mock_client = MagicMock()
        mock_client.get.side_effect = [
            httpx.HTTPStatusError(
                "Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            ),
            httpx.HTTPStatusError(
                "Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=502),
            ),
            httpx.HTTPStatusError(
                "Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=503),
            ),
        ]

        scraper = SyosetsuScraper(client=mock_client)
        with pytest.raises(httpx.HTTPStatusError):
            scraper._fetch("https://example.com/test")

        assert mock_client.get.call_count == 3

    @patch("scrapers.syosetsu.time.sleep")
    def test_uses_exponential_backoff(self, mock_sleep: MagicMock) -> None:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "<html>ok</html>"

        mock_client.get.side_effect = [
            httpx.HTTPStatusError(
                "Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            ),
            httpx.HTTPStatusError(
                "Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            ),
            mock_response,
        ]

        scraper = SyosetsuScraper(client=mock_client)
        scraper._fetch("https://example.com/test")

        # Exponential backoff: 2^0=1s, 2^1=2s
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)
        assert mock_sleep.call_count == 2
