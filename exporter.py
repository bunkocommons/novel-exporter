"""Novel exporter CLI - download and export novels from various sources."""

import argparse
import re
import sys
from pathlib import Path

from exporters import EpubExporter, PdfExporter, TxtExporter
from scrapers import KakuyomuScraper, SyosetsuScraper

SCRAPERS = [SyosetsuScraper(), KakuyomuScraper()]
EXPORTERS = {
    "epub": EpubExporter(),
    "pdf": PdfExporter(),
    "txt": TxtExporter(),
}


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = name.strip(". ")
    return name or "untitled"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download novels and export to various formats."
    )
    parser.add_argument("url", help="Novel URL to download")
    parser.add_argument(
        "--format",
        choices=["epub", "pdf", "txt"],
        default="epub",
        help="Export format (default: epub)",
    )
    parser.add_argument(
        "--output-dir",
        default="exports",
        help="Output directory (default: exports/)",
    )

    args = parser.parse_args()

    # Find appropriate scraper
    scraper = None
    for s in SCRAPERS:
        if s.can_handle(args.url):
            scraper = s
            break

    if scraper is None:
        print(f"Error: No scraper available for URL: {args.url}", file=sys.stderr)
        return 1

    print(f"Scraping: {args.url}")

    try:
        novel = scraper.scrape(args.url)
    except Exception as e:
        print(f"Error during scraping: {e}", file=sys.stderr)
        return 1

    print(f"Downloaded: {novel.title} by {novel.author}")
    print(f"Chapters: {len(novel.chapters)}")

    # Export
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = sanitize_filename(novel.title)
    filepath = output_dir / f"{filename}.{args.format}"

    exporter = EXPORTERS[args.format]

    print(f"Exporting to {args.format.upper()}...")
    try:
        exporter.export(novel, str(filepath))
    except Exception as e:
        print(f"Error during export: {e}", file=sys.stderr)
        return 1

    print(f"Saved: {filepath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
