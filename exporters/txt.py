"""Plain text exporter."""

from pathlib import Path

from exporters.base import BaseExporter
from models import Novel


class TxtExporter(BaseExporter):
    """Export novels to plain text format."""

    def export(self, novel: Novel, filepath: str) -> None:
        lines = [
            novel.title,
            "",
            f"作者：{novel.author}",
        ]

        if novel.published_date:
            lines.append(f"掲載日：{novel.published_date.isoformat()}")

        lines.extend([
            "",
            "=" * 40,
            "",
        ])

        for chapter in novel.chapters:
            lines.extend([
                "",
                chapter.title,
                "",
            ])
            lines.extend(chapter.text.split("\n"))
            lines.extend(["", "-" * 40])

        # Source attribution at the end
        lines.extend([
            "",
            "=" * 40,
            "",
            "出典",
            "この作品は以下のサイトから取得しました。",
            novel.source_url,
            "",
        ])

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
