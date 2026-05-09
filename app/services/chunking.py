"""
Chunking by spans.

Walks the parser output and accumulates spans into chunks of approximately
`chunk_size` characters. When a chunk fills up, the next chunk starts with
some overlap (carried-over spans whose total text is roughly `overlap` chars).

Each chunk carries:
  - content: concatenated text of its spans
  - page_num: page where it starts
  - page_width, page_height: from that page
  - bboxes: list of [x0, y0, x1, y1] for every span that contributed

This keeps highlights precise: the bboxes ARE the spans that produced the
chunk's text. No search, no matching, no false positives.
"""

import uuid
from app.models.chunk import Chunk


def text_splitter(chunk_size: int, overlap: int, document_id: uuid.UUID, pages: list):
    """
    Args:
        chunk_size: target characters per chunk
        overlap: characters of overlap with the previous chunk
        document_id: uuid for foreign key
        pages: parser output (see parsing.py docstring)

    Returns:
        list of Chunk objects ready to be added to the DB session
    """
    chunks = []
    chunk_index = 0

    # Buffer for the chunk we're currently building
    current_text_parts: list[str] = []
    current_bboxes: list[list[float]] = []
    current_length = 0
    current_page_num: int | None = None
    current_page_width: int | None = None
    current_page_height: int | None = None

    def flush():
        """Emit the buffered spans as one Chunk, if there's anything to emit."""
        nonlocal chunk_index
        if not current_text_parts:
            return None

        content = " ".join(current_text_parts).strip()
        if not content:
            return None

        # bboxes are only meaningful when we have ALL of them with coords.
        # If any span had bbox=None (DOCX), we drop the whole list — the
        # frontend treats this as "highlighting unavailable".
        bboxes_for_chunk = (
            current_bboxes if all(b is not None for b in current_bboxes) and current_bboxes
            else None
        )

        chunk = Chunk(
            doc_id=document_id,
            content=content,
            chunk_index=chunk_index,
            page_num=current_page_num if current_page_num is not None else 0,
            start_char=0,  # legacy field, no longer meaningful
            end_char=len(content),
            bboxes=bboxes_for_chunk,
            page_width=current_page_width,
            page_height=current_page_height,
        )
        chunks.append(chunk)
        chunk_index += 1
        return chunk

    def carry_overlap():
        """
        After flushing, prepare the buffer with overlap from the just-emitted chunk.
        Walks backward through the buffer, keeping spans whose total text is
        ~overlap chars. This means subsequent retrievals see continuity at chunk
        boundaries.
        """
        nonlocal current_text_parts, current_bboxes, current_length

        if overlap <= 0 or not current_text_parts:
            current_text_parts = []
            current_bboxes = []
            current_length = 0
            return

        # Walk backward, accumulating until we have ~overlap chars
        kept_text = []
        kept_bboxes = []
        kept_length = 0
        for text, bbox in zip(reversed(current_text_parts), reversed(current_bboxes)):
            if kept_length >= overlap:
                break
            kept_text.insert(0, text)
            kept_bboxes.insert(0, bbox)
            kept_length += len(text) + 1  # +1 for the joining space

        current_text_parts = kept_text
        current_bboxes = kept_bboxes
        current_length = kept_length

    for page in pages:
        page_num = page["page_num"]
        page_width = page["page_width"]
        page_height = page["page_height"]

        # HARD PAGE BOUNDARY: a chunk must never contain spans from multiple
        # pages. Bboxes are page-relative, so mixing them would point highlights
        # to wrong locations. If we already have buffered content from a previous
        # page, flush before starting this page. We do NOT carry overlap across
        # pages — overlap only makes sense within a single visual context.
        if current_text_parts and current_page_num != page_num:
            flush()
            # Reset buffer entirely; no overlap across page boundaries.
            current_text_parts = []
            current_bboxes = []
            current_length = 0

        for span in page["spans"]:
            span_text = span["text"]
            span_bbox = span["bbox"]
            span_length = len(span_text) + 1  # +1 for joining space

            # If this is the first span of a new buffer, anchor the page metadata.
            if not current_text_parts:
                current_page_num = page_num
                current_page_width = page_width
                current_page_height = page_height

            # If adding this span would exceed chunk_size AND we already have
            # content, flush the current chunk and start a new one with overlap.
            if current_length + span_length > chunk_size and current_text_parts:
                flush()
                carry_overlap()
                # carry_overlap() may have left some spans in the buffer.
                # If empty, anchor new chunk to current page metadata.
                if not current_text_parts:
                    current_page_num = page_num
                    current_page_width = page_width
                    current_page_height = page_height

            current_text_parts.append(span_text)
            current_bboxes.append(span_bbox)
            current_length += span_length

    # Flush any trailing buffer
    flush()

    return chunks