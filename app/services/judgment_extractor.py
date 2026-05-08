"""Extract text from uploaded judgment files (PDF / DOCX).

Scope (v1): digital text only — no OCR. If the user uploads a scanned PDF
(image-based, no embedded text), we raise ScannedPdfError with an Arabic
message instructing them to provide a text version.

Future v2: pass scanned-PDF pages to Claude vision for OCR + analysis in
one call. Hooks for that are intentionally left in place (see
ScannedPdfError handling in routes).
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass


# Anything below this threshold on a non-trivial PDF (>=1 page) suggests the
# file is a scan with no embedded text. Real digital judgments easily clear
# 200 chars even on a single short page.
_MIN_USEFUL_CHARS_PER_PAGE = 80
# Cap text we send to Claude. Most judgments are under ~30K chars; a hard cap
# keeps us under Haiku's input limits and bounds cost predictably.
MAX_CHARS = 60_000


class ExtractionError(Exception):
    """Generic extraction failure — message is in Arabic, safe to show user."""


class UnsupportedFileTypeError(ExtractionError):
    pass


class ScannedPdfError(ExtractionError):
    """Raised when a PDF appears to be scanned (no embedded text)."""


@dataclass
class ExtractResult:
    text: str
    page_count: int
    char_count: int
    source: str  # 'pdf' | 'docx'


# ── PDF ───────────────────────────────────────────────────────────────────────

def _extract_pdf(path: str) -> ExtractResult:
    import fitz  # PyMuPDF — best Arabic / RTL handling per 2026 evals

    doc = fitz.open(path)
    try:
        pages = []
        for page in doc:
            # "text" sort=True gives reading-order output, which on RTL Arabic
            # PDFs is what we actually want. Without sort, columns interleave.
            pages.append(page.get_text("text", sort=True))
        text = "\n\n".join(pages).strip()
        page_count = doc.page_count
    finally:
        doc.close()

    if page_count == 0:
        raise ExtractionError('الملف فارغ أو تالف — يرجى المحاولة بنسخة أخرى')

    if len(text) < _MIN_USEFUL_CHARS_PER_PAGE * page_count:
        raise ScannedPdfError(
            'يبدو أن هذا الملف نسخة ممسوحة ضوئياً (صور) ولا يحتوي على نص قابل '
            'للاستخراج. يرجى رفع نسخة نصية من الحكم، أو إدخال البيانات يدوياً.'
        )

    return ExtractResult(
        text=text[:MAX_CHARS], page_count=page_count,
        char_count=len(text), source='pdf',
    )


# ── DOCX ──────────────────────────────────────────────────────────────────────

def _extract_docx(path: str) -> ExtractResult:
    from docx import Document  # python-docx, already in requirements

    doc = Document(path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    # Tables (used for case headers in many Arabic judgment templates)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                cell_text = cell.text.strip()
                if cell_text:
                    paragraphs.append(cell_text)

    text = "\n".join(paragraphs).strip()
    if not text:
        raise ExtractionError('الملف لا يحتوي على نص — يرجى المحاولة بنسخة أخرى')

    return ExtractResult(
        text=text[:MAX_CHARS], page_count=0,
        char_count=len(text), source='docx',
    )


# ── Public API ────────────────────────────────────────────────────────────────

_PDF_EXTS = {'.pdf'}
_DOCX_EXTS = {'.docx'}
SUPPORTED_EXTS = _PDF_EXTS | _DOCX_EXTS


def extract_text(file_path: str) -> ExtractResult:
    """Detect type and extract. Raises ExtractionError subclasses on failure.

    All error messages are Arabic and safe to surface to the end user.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext in _PDF_EXTS:
        return _extract_pdf(file_path)
    if ext in _DOCX_EXTS:
        return _extract_docx(file_path)
    raise UnsupportedFileTypeError(
        'نوع الملف غير مدعوم — يرجى رفع PDF أو DOCX فقط'
    )
