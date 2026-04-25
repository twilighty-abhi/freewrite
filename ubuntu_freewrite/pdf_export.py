from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from .models import HumanEntry


def extract_title_from_content(content: str, date_label: str) -> str:
    trimmed = content.strip()
    if not trimmed:
        return f"Entry {date_label}"

    words = [
        word.strip(".,!?;:\"'()[]{}<>").lower()
        for word in trimmed.replace("\n", " ").split()
    ]
    words = [word for word in words if word]

    if len(words) >= 4:
        return "-".join(words[:4])
    if words:
        return "-".join(words)
    return f"Entry {date_label}"


def export_text_to_pdf(text: str, output_path: Path, font_name: str = "Helvetica", font_size: int = 18, line_spacing: float = 1.5) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(output_path), pagesize=letter)
    width, height = letter
    margin = 72
    usable_width = width - (margin * 2)
    x = margin
    y = height - margin
    line_height = font_size * line_spacing

    pdf.setTitle(output_path.stem)
    pdf.setAuthor("Freewrite Ubuntu")
    resolved_font = resolve_pdf_font_name(font_name)
    pdf.setFont(resolved_font, font_size)

    for paragraph in text.strip().splitlines() or [""]:
        wrapped_lines = wrap_text(paragraph, usable_width, pdf, resolved_font, font_size)
        if not wrapped_lines:
            wrapped_lines = [""]
        for line in wrapped_lines:
            if y <= margin:
                pdf.showPage()
                pdf.setFont(resolved_font, font_size)
                y = height - margin
            pdf.drawString(x, y, line)
            y -= line_height
        y -= line_height * 0.25

    pdf.save()


def resolve_pdf_font_name(ui_font_name: str) -> str:
    """
    Map Qt/UI font family names to a font that ReportLab can actually use.

    ReportLab supports the Base 14 fonts out of the box; everything else needs
    explicit TTF registration. We prefer a safe fallback rather than failing
    PDF export.
    """
    if not ui_font_name:
        return "Helvetica"

    normalized = ui_font_name.strip().lower()
    known_map = {
        "sans serif": "Helvetica",
        "sans-serif": "Helvetica",
        "system": "Helvetica",
        "arial": "Helvetica",
        "times new roman": "Times-Roman",
        "serif": "Times-Roman",
        "monospace": "Courier",
    }
    candidate = known_map.get(normalized, ui_font_name.strip())

    # Base 14 fonts are always available; otherwise check registered fonts.
    base14 = {
        "Courier",
        "Courier-Bold",
        "Courier-Oblique",
        "Courier-BoldOblique",
        "Helvetica",
        "Helvetica-Bold",
        "Helvetica-Oblique",
        "Helvetica-BoldOblique",
        "Times-Roman",
        "Times-Bold",
        "Times-Italic",
        "Times-BoldItalic",
        "Symbol",
        "ZapfDingbats",
    }
    if candidate in base14:
        return candidate

    if candidate in set(pdfmetrics.getRegisteredFontNames()):
        return candidate

    return "Helvetica"


def wrap_text(text: str, width: float, pdf: canvas.Canvas, font_name: str, font_size: int) -> list[str]:
    if not text:
        return []

    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if pdf.stringWidth(candidate, font_name, font_size) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines
