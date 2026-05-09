"""
Document parsing.

Output shape (uniform across formats):
    [
        {
            "page_num": int,                      # 0-indexed
            "page_width": int | None,             # in points; None for DOCX
            "page_height": int | None,
            "spans": [
                {
                    "text": str,
                    "bbox": [x0, y0, x1, y1] | None,   # browser coords; None for DOCX
                },
                ...
            ],
        },
        ...
    ]

A "span" is the smallest unit of text returned by the parser. For PDFs, it's
typically a paragraph block (PyMuPDF's "blocks" mode). For DOCX, it's a
paragraph. The chunker walks these spans and accumulates them into chunks.
"""

import logging
import uuid
import fitz  # PyMuPDF
from docx import Document as DocxDocument
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.document import Document

logger = logging.getLogger(__name__)


async def parse_document(document_id: uuid.UUID, db: AsyncSession):
    doc = await db.get(Document, document_id)
    if not doc:
        logger.error(f"parse_document: document {document_id} not found")
        return None

    if doc.file_type == ".pdf":
        return _parse_pdf(doc.file_path)
    elif doc.file_type == ".docx":
        return _parse_docx(doc.file_path)
    else:
        logger.error(f"parse_document: unsupported file type {doc.file_type}")
        return None


def _parse_pdf(file_path: str):
    """
    Extract structured text from a PDF using PyMuPDF.

    Each block from `page.get_text("blocks")` is one paragraph-ish unit
    with its bounding box. We turn each into a span.
    """
    pages = []
    with fitz.open(file_path) as pdf:
        for page_num, page in enumerate(pdf):
            # get_text("blocks") returns tuples of:
            #   (x0, y0, x1, y1, text, block_no, block_type)
            # block_type 0 == text, 1 == image. We want only text.
            blocks = page.get_text("blocks")

            spans = []
            for x0, y0, x1, y1, text, _block_no, block_type in blocks:
                if block_type != 0:  # skip images
                    continue
                cleaned = text.strip()
                if not cleaned:
                    continue
                spans.append({
                    "text": cleaned,
                    "bbox": [
                        round(x0, 2),
                        round(y0, 2),
                        round(x1, 2),
                        round(y1, 2),
                    ],
                })

            pages.append({
                "page_num": page_num,
                "page_width": round(page.rect.width),
                "page_height": round(page.rect.height),
                "spans": spans,
            })

    return pages


def _parse_docx(file_path: str):
    """
    Extract paragraphs from a DOCX. No spatial info available — bbox is None.

    DOCX has no "pages" concept (pagination is computed by the renderer at
    open time, not stored), so we put everything on page 0.
    """
    docx = DocxDocument(file_path)

    spans = []
    for para in docx.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        spans.append({
            "text": text,
            "bbox": None,
        })

    # Single virtual page
    return [{
        "page_num": 0,
        "page_width": None,
        "page_height": None,
        "spans": spans,
    }]