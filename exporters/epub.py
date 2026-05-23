"""EPUB exporter using ebooklib."""

import re
from pathlib import Path

from ebooklib import epub

from exporters.base import BaseExporter
from models import Novel


class EpubExporter(BaseExporter):
    """Export novels to EPUB format with proper reading margins."""

    def export(self, novel: Novel, filepath: str) -> None:
        book = epub.EpubBook()

        book.set_identifier(
            f"novel-exporter-{novel.source}-{self._sanitize(novel.title)}"
        )
        book.set_title(novel.title)
        book.set_language("ja")
        book.add_author(novel.author)

        # Add CSS for proper reading margins and typography
        style_content = """
        @page {
            margin: 5%;
        }
        body {
            font-family: "Hiragino Mincho ProN", "Yu Mincho", "MS Mincho", serif;
            font-size: 1.1em;
            line-height: 1.8;
            margin: 5%;
            padding: 0;
            color: #333;
        }
        h1 {
            font-size: 1.5em;
            text-align: center;
            margin-top: 2em;
            margin-bottom: 1.5em;
            font-weight: bold;
            page-break-before: always;
        }
        h1:first-of-type {
            page-break-before: auto;
        }
        p {
            text-indent: 1em;
            margin: 0;
            padding: 0;
        }
        .meta {
            text-align: center;
            margin-bottom: 0.5em;
            text-indent: 0;
        }
        .meta-label {
            color: #666;
            font-size: 0.9em;
        }
        .source-section {
            margin-top: 3em;
            padding-top: 1em;
            border-top: 1px solid #ccc;
            page-break-before: always;
        }
        .source-section h2 {
            font-size: 1.2em;
            text-align: center;
            margin-bottom: 1em;
        }
        .source-section p {
            text-indent: 0;
            text-align: center;
            word-break: break-all;
        }
        """

        style = epub.EpubItem(
            uid="style",
            file_name="style.css",
            media_type="text/css",
            content=style_content,
        )
        book.add_item(style)

        # Build chapters
        spine = []
        toc = []

        for idx, chapter in enumerate(novel.chapters):
            file_name = f"chapter_{idx:04d}.xhtml"
            html_title = self._escape_html(chapter.title)

            # Convert plain text to HTML paragraphs
            paragraphs = []
            for line in chapter.text.split("\n"):
                line = line.strip()
                if line:
                    escaped = self._escape_html(line)
                    paragraphs.append(f"<p>{escaped}</p>")

            body_html = "\n".join(paragraphs)

            # For the first chapter, prepend title page metadata
            if idx == 0:
                meta_parts = [
                    f'<p class="meta"><span class="meta-label">作者：</span>{self._escape_html(novel.author)}</p>',
                ]
                if novel.published_date:
                    meta_parts.append(
                        f'<p class="meta"><span class="meta-label">掲載日：</span>{novel.published_date.isoformat()}</p>'
                    )
                meta_html = "\n".join(meta_parts)
                body_html = f"{meta_html}\n{body_html}"

            # For the last chapter, append source section
            if idx == len(novel.chapters) - 1:
                source_html = f"""
<div class="source-section">
<h2>出典</h2>
<p>この作品は以下のサイトから取得しました。</p>
<p>{self._escape_html(novel.source_url)}</p>
</div>"""
                body_html = f"{body_html}\n{source_html}"

            content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="UTF-8"/>
<title>{html_title}</title>
<link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
<h1>{html_title}</h1>
{body_html}
</body>
</html>"""

            epub_chapter = epub.EpubHtml(
                title=chapter.title,
                file_name=file_name,
                lang="ja",
            )
            epub_chapter.set_content(content.encode("utf-8"))
            epub_chapter.add_item(style)

            book.add_item(epub_chapter)
            spine.append(epub_chapter)
            toc.append(epub_chapter)

        book.toc = toc
        book.spine = spine

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        epub.write_epub(filepath, book)

    @staticmethod
    def _sanitize(text: str) -> str:
        return re.sub(r"[^\w\s-]", "", text).strip()

    @staticmethod
    def _escape_html(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
