"""PDF exporter using reportlab."""

import os
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from exporters.base import BaseExporter
from models import Novel

# Common system fonts with CJK support
_FONT_CANDIDATES = [
    # macOS
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    # Linux
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-JP-Regular.otf",
    # Windows
    "C:/Windows/Fonts/msgothic.ttc",
    "C:/Windows/Fonts/yumin.ttf",
    "C:/Windows/Fonts/msmincho.ttc",
]


def _find_cjk_font() -> str | None:
    """Find a system font with CJK support."""
    for path in _FONT_CANDIDATES:
        if os.path.isfile(path):
            return path
    return None


class PdfExporter(BaseExporter):
    """Export novels to PDF format with proper margins."""

    def __init__(self) -> None:
        self.font_name = "Helvetica"
        self.font_name_bold = "Helvetica-Bold"

        font_path = _find_cjk_font()
        if font_path:
            try:
                # Register the font with reportlab
                pdfmetrics.registerFont(TTFont("CJKFont", font_path, subfontIndex=0))
                self.font_name = "CJKFont"
                self.font_name_bold = "CJKFont"
            except Exception:
                pass

    def export(self, novel: Novel, filepath: str) -> None:
        doc = SimpleDocTemplate(
            filepath,
            pagesize=A5,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
        )

        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                "Japanese",
                parent=styles["BodyText"],
                fontName=self.font_name,
                fontSize=11,
                leading=20,
                firstLineIndent=18,
                spaceAfter=6,
            )
        )
        styles.add(
            ParagraphStyle(
                "ChapterTitle",
                parent=styles["Heading1"],
                fontName=self.font_name_bold,
                fontSize=14,
                leading=24,
                alignment=1,  # center
                spaceBefore=30,
                spaceAfter=20,
            )
        )
        styles.add(
            ParagraphStyle(
                "NovelTitle",
                parent=styles["Title"],
                fontName=self.font_name_bold,
                fontSize=18,
                leading=30,
                alignment=1,  # center
                spaceBefore=60,
            )
        )
        styles.add(
            ParagraphStyle(
                "MetaInfo",
                parent=styles["Normal"],
                fontName=self.font_name,
                fontSize=11,
                leading=18,
                alignment=1,  # center
                spaceAfter=6,
            )
        )
        styles.add(
            ParagraphStyle(
                "MetaLabel",
                parent=styles["Normal"],
                fontName=self.font_name,
                fontSize=10,
                leading=16,
                alignment=1,  # center
                textColor=HexColor("#666666"),
                spaceAfter=2,
            )
        )
        styles.add(
            ParagraphStyle(
                "SourceSection",
                parent=styles["Heading2"],
                fontName=self.font_name_bold,
                fontSize=12,
                leading=20,
                alignment=1,  # center
                spaceBefore=40,
                spaceAfter=12,
            )
        )
        styles.add(
            ParagraphStyle(
                "SourceText",
                parent=styles["Normal"],
                fontName=self.font_name,
                fontSize=9,
                leading=14,
                alignment=1,  # center
                textColor=HexColor("#333333"),
            )
        )

        story = []

        # Title page
        story.append(Paragraph(novel.title, styles["NovelTitle"]))

        # Author and published date below title
        story.append(Paragraph(f"作者：{novel.author}", styles["MetaInfo"]))
        if novel.published_date:
            story.append(
                Paragraph(
                    f"掲載日：{novel.published_date.isoformat()}",
                    styles["MetaInfo"],
                )
            )

        story.append(Spacer(1, 30))

        # Chapters
        for chapter in novel.chapters:
            story.append(Paragraph(chapter.title, styles["ChapterTitle"]))

            for line in chapter.text.split("\n"):
                line = line.strip()
                if line:
                    escaped = self._escape_xml(line)
                    story.append(Paragraph(escaped, styles["Japanese"]))

            story.append(Spacer(1, 20))

        # Source attribution at the end
        story.append(Paragraph("出典", styles["SourceSection"]))
        story.append(
            Paragraph("この作品は以下のサイトから取得しました。", styles["SourceText"])
        )
        story.append(Paragraph(novel.source_url, styles["SourceText"]))

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        doc.build(story)

    @staticmethod
    def _escape_xml(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
