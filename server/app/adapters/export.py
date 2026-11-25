"""Render structured report blocks to PDF (fpdf2) or DOCX (python-docx).

Reusable by every module (dossiers, payslips, voucher prints, document export)::

    report = Report(title="Batch Summary", blocks=[...], letterhead=Letterhead(name="Acme", lines=[...]))
    pdf_bytes = get_exporter().render(report, "pdf")

Block types: heading{text,level} paragraph{text} kv{rows:[{label,value}]} table{columns,rows}
qc_table{columns,rows} (falls back to text) signature{roles} divider{} page_break{} image{ref,width_mm}
(``ref`` looks up ``Report.images``). Text is rendered as plain text (no markup/code execution).
DejaVu Sans is bundled so ₹ and other Unicode render correctly.
"""

from __future__ import annotations

import abc
import io
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

FONT_DIR = Path(__file__).parent / "fonts"
PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@dataclass
class Letterhead:
    name: str
    lines: list[str] = field(default_factory=list)  # address, GSTIN, contact
    logo: bytes | None = None


@dataclass
class Report:
    title: str
    blocks: list[dict[str, Any]]
    letterhead: Letterhead | None = None
    footer: str | None = None
    watermark: str | None = None  # e.g. "OBSOLETE"
    images: dict[str, bytes] = field(default_factory=dict)
    landscape: bool = False


def _s(value: Any) -> str:
    return "" if value is None else str(value)


class DocumentExportProvider(abc.ABC):
    @abc.abstractmethod
    def render_pdf(self, report: Report) -> bytes: ...

    @abc.abstractmethod
    def render_docx(self, report: Report) -> bytes: ...

    def render(self, report: Report, fmt: str) -> bytes:
        if fmt.lower() == "pdf":
            return self.render_pdf(report)
        if fmt.lower() == "docx":
            return self.render_docx(report)
        raise ValueError(f"unsupported export format {fmt!r}")

    @staticmethod
    def mime(fmt: str) -> str:
        return PDF_MIME if fmt.lower() == "pdf" else DOCX_MIME


class FpdfDocxExporter(DocumentExportProvider):
    # ------------------------------------------------------------ PDF
    def render_pdf(self, report: Report) -> bytes:
        from fpdf import FPDF
        from fpdf.enums import XPos, YPos

        footer_text = report.footer
        watermark = report.watermark

        class _PDF(FPDF):
            def footer(self) -> None:  # noqa: D401
                self.set_y(-12)
                self.set_font("DejaVu", "", 8)
                self.set_text_color(102, 112, 133)
                self.cell(0, 6, f"{footer_text or ''}   Page {self.page_no()}/{{nb}}", align="C")
                self.set_text_color(0, 0, 0)

            def header(self) -> None:
                if watermark:
                    self.set_font("DejaVu", "B", 48)
                    self.set_text_color(235, 236, 240)
                    with self.rotation(35, x=self.w / 2, y=self.h / 2):
                        self.text(self.w / 2 - 60, self.h / 2, watermark)
                    self.set_text_color(0, 0, 0)

        pdf = _PDF(orientation="L" if report.landscape else "P", unit="mm", format="A4")
        pdf.add_font("DejaVu", "", str(FONT_DIR / "DejaVuSans.ttf"))
        pdf.add_font("DejaVu", "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
        pdf.set_auto_page_break(auto=True, margin=16)
        pdf.alias_nb_pages()
        pdf.add_page()
        nl = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}

        if report.letterhead:
            lh = report.letterhead
            if lh.logo:
                try:
                    pdf.image(io.BytesIO(lh.logo), x=pdf.l_margin, y=10, h=14)
                    pdf.set_xy(pdf.l_margin + 30, 10)
                except Exception:  # noqa: BLE001,S110 - a bad logo must not break the export
                    pass
            pdf.set_font("DejaVu", "B", 13)
            pdf.cell(0, 7, lh.name, **nl)
            pdf.set_font("DejaVu", "", 8)
            for line in lh.lines:
                pdf.set_x(pdf.l_margin + (30 if lh.logo else 0))
                pdf.cell(0, 4, line, **nl)
            pdf.ln(2)
            pdf.set_draw_color(234, 236, 240)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(3)

        pdf.set_font("DejaVu", "B", 15)
        pdf.multi_cell(0, 8, report.title, **nl)
        pdf.ln(2)

        for block in report.blocks:
            t, data = block.get("type"), block.get("data") or {}
            if t == "heading":
                size = {1: 14, 2: 12, 3: 11}.get(int(data.get("level", 2)), 11)
                pdf.set_font("DejaVu", "B", size)
                pdf.multi_cell(0, 6, _s(data.get("text")), **nl)
                pdf.ln(1)
            elif t == "paragraph":
                pdf.set_font("DejaVu", "", 10)
                pdf.multi_cell(0, 5, _s(data.get("text")), **nl)
                pdf.ln(1)
            elif t == "kv":
                pdf.set_font("DejaVu", "", 9)
                rows = [[_s(r.get("label")), _s(r.get("value"))] for r in data.get("rows", [])]
                if rows:
                    with pdf.table(col_widths=(35, 65), first_row_as_headings=False, line_height=5) as table:
                        for r in rows:
                            table.row(r)
                pdf.ln(2)
            elif t in ("table", "qc_table") and data.get("columns"):
                pdf.set_font("DejaVu", "", 8)
                with pdf.table(line_height=5) as table:
                    table.row([_s(c) for c in data["columns"]])
                    for r in data.get("rows", []):
                        table.row([_s(c) for c in r])
                pdf.ln(2)
            elif t == "qc_table":
                pdf.set_font("DejaVu", "", 9)
                pdf.multi_cell(0, 5, _s(data.get("text")), **nl)
            elif t == "signature":
                pdf.ln(8)
                pdf.set_font("DejaVu", "", 9)
                roles = data.get("roles") or []
                width = (pdf.w - pdf.l_margin - pdf.r_margin) / max(len(roles), 1)
                for _role in roles:
                    pdf.cell(width, 5, "______________________", align="C")
                pdf.ln(5)
                for role in roles:
                    signer = (data.get("signers") or {}).get(role, "")
                    pdf.cell(width, 5, f"{role}{(': ' + signer) if signer else ''}", align="C")
                pdf.ln(6)
            elif t == "divider":
                pdf.ln(1)
                pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
                pdf.ln(2)
            elif t == "page_break":
                pdf.add_page()
            elif t == "image":
                img = report.images.get(_s(data.get("ref")))
                if img:
                    pdf.image(io.BytesIO(img), w=float(data.get("width_mm", 120)))
                    pdf.ln(2)
        return bytes(pdf.output())

    # ------------------------------------------------------------ DOCX
    def render_docx(self, report: Report) -> bytes:
        from docx import Document
        from docx.shared import Mm, Pt

        doc = Document()
        style = doc.styles["Normal"]
        style.font.name = "DejaVu Sans"
        style.font.size = Pt(10)
        if report.letterhead:
            lh = report.letterhead
            if lh.logo:
                try:
                    doc.add_picture(io.BytesIO(lh.logo), height=Mm(14))
                except Exception:  # noqa: BLE001,S110
                    pass
            p = doc.add_paragraph()
            run = p.add_run(lh.name)
            run.bold = True
            run.font.size = Pt(13)
            for line in lh.lines:
                doc.add_paragraph(line).runs[0].font.size = Pt(8)
        if report.watermark:
            doc.add_paragraph(f"[{report.watermark}]").runs[0].bold = True
        doc.add_heading(report.title, level=1)
        for block in report.blocks:
            t, data = block.get("type"), block.get("data") or {}
            if t == "heading":
                doc.add_heading(_s(data.get("text")), level=min(max(int(data.get("level", 2)), 1), 4))
            elif t == "paragraph":
                doc.add_paragraph(_s(data.get("text")))
            elif t == "kv":
                rows = data.get("rows", [])
                if rows:
                    table = doc.add_table(rows=0, cols=2)
                    table.style = "Table Grid"
                    for r in rows:
                        cells = table.add_row().cells
                        cells[0].text, cells[1].text = _s(r.get("label")), _s(r.get("value"))
            elif t in ("table", "qc_table") and data.get("columns"):
                cols = data["columns"]
                table = doc.add_table(rows=1, cols=len(cols))
                table.style = "Table Grid"
                for i, c in enumerate(cols):
                    table.rows[0].cells[i].text = _s(c)
                for r in data.get("rows", []):
                    cells = table.add_row().cells
                    for i, c in enumerate(r[: len(cols)]):
                        cells[i].text = _s(c)
            elif t == "qc_table":
                doc.add_paragraph(_s(data.get("text")))
            elif t == "signature":
                roles = data.get("roles") or []
                if roles:
                    table = doc.add_table(rows=2, cols=len(roles))
                    for i, role in enumerate(roles):
                        table.rows[0].cells[i].text = "\n\n______________________"
                        table.rows[1].cells[i].text = role
            elif t == "divider":
                doc.add_paragraph("_" * 60)
            elif t == "page_break":
                doc.add_page_break()
            elif t == "image":
                img = report.images.get(_s(data.get("ref")))
                if img:
                    doc.add_picture(io.BytesIO(img), width=Mm(float(data.get("width_mm", 120))))
        if report.footer:
            doc.sections[0].footer.paragraphs[0].text = report.footer
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()


@lru_cache
def get_exporter() -> DocumentExportProvider:
    return FpdfDocxExporter()
