from io import BytesIO
import os
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from calculus_agent.schemas import PaperPreviewRead

FONT = "MathPaperCJK"
_FONT_CANDIDATES = [
    os.getenv("MATH_PAPER_FONT_PATH"),
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]
_font_path = next((path for path in _FONT_CANDIDATES if path and Path(path).is_file()), None)
if _font_path is None:
    raise RuntimeError("未找到中文字体，请设置 MATH_PAPER_FONT_PATH")
pdfmetrics.registerFont(TTFont(FONT, _font_path))


def render_paper_pdf(paper: PaperPreviewRead, *, teacher_version: bool) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=paper.title,
        author="Math Paper Agent",
    )
    styles = _styles()
    story = [
        Paragraph(
            escape(paper.title + (" - 教师解析卷" if teacher_version else "")), styles["title"]
        ),
        Spacer(1, 4 * mm),
        Table(
            [["姓名：________________", "班级：________________", f"满分：{paper.total_score} 分"]],
            colWidths=[60 * mm, 60 * mm, 45 * mm],
            style=TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), FONT),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ]
            ),
        ),
        Spacer(1, 7 * mm),
    ]
    current_type = None
    for index, item in enumerate(paper.items, start=1):
        if item.question_type != current_type:
            current_type = item.question_type
            story.extend(
                [
                    Paragraph(escape(current_type), styles["section"]),
                    Spacer(1, 2 * mm),
                ]
            )
        story.append(
            Paragraph(
                f"{index}. {escape(item.question_text)} <font color='#64748B'>（{item.score}分）</font>",
                styles["question"],
            )
        )
        story.append(Spacer(1, 10 * mm if item.question_type == "解答题" else 5 * mm))

    if teacher_version:
        story.extend([PageBreak(), Paragraph("参考答案与解析", styles["title"]), Spacer(1, 6 * mm)])
        for index, item in enumerate(paper.items, start=1):
            story.append(Paragraph(f"第 {index} 题", styles["answer_title"]))
            story.append(
                Paragraph(f"答案：{escape(item.final_answer or '暂无独立答案')}", styles["answer"])
            )
            for step_index, step in enumerate(item.solution_steps, start=1):
                story.append(Paragraph(f"{step_index}. {escape(step)}", styles["answer"]))
            if item.knowledge:
                story.append(
                    Paragraph(f"知识点：{escape('、'.join(item.knowledge))}", styles["meta"])
                )
            story.append(Spacer(1, 5 * mm))

    doc.build(story, onFirstPage=_page_number, onLaterPages=_page_number)
    return buffer.getvalue()


def _styles() -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle(
            "title",
            fontName=FONT,
            fontSize=20,
            leading=28,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#0F172A"),
        ),
        "section": ParagraphStyle(
            "section",
            fontName=FONT,
            fontSize=13,
            leading=20,
            spaceBefore=5,
            textColor=colors.HexColor("#1D4ED8"),
            borderColor=colors.HexColor("#93C5FD"),
            borderWidth=0,
            borderPadding=(3, 0, 3, 7),
            leftIndent=0,
        ),
        "question": ParagraphStyle(
            "question",
            fontName=FONT,
            fontSize=11,
            leading=20,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#111827"),
            wordWrap="CJK",
        ),
        "answer_title": ParagraphStyle(
            "answer_title",
            fontName=FONT,
            fontSize=12,
            leading=20,
            textColor=colors.HexColor("#1D4ED8"),
            spaceAfter=3,
        ),
        "answer": ParagraphStyle(
            "answer",
            fontName=FONT,
            fontSize=10.5,
            leading=18,
            textColor=colors.HexColor("#1F2937"),
            wordWrap="CJK",
        ),
        "meta": ParagraphStyle(
            "meta",
            fontName=FONT,
            fontSize=9,
            leading=16,
            textColor=colors.HexColor("#64748B"),
            wordWrap="CJK",
        ),
    }


def _page_number(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont(FONT, 9)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawCentredString(A4[0] / 2, 10 * mm, f"第 {doc.page} 页")
    canvas.restoreState()
