#!/usr/bin/env python3
"""LLM-assisted golden dataset generation from fixture chunks."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.models.chunk import Chunk
from app.services.llm_errors import raise_llm_http_error
from eval.paths import GOLDEN_DATASET_PATH, GOLDEN_MARKDOWN_PATH
from eval.schemas import EvalItem
from eval.state import load_fixture_state


class EvalGenerationResult(BaseModel):
    items: list[EvalItem] = Field(min_length=1)


class RefineBatch(BaseModel):
    kept_indices: list[int] = Field(
        description="Indices of strong eval items to keep (0-based)"
    )


def _format_chunks_for_prompt(chunks: list[Chunk], max_chars: int = 400) -> str:
    lines = []
    for chunk in chunks:
        content = (chunk.content or "").strip().replace("\n", " ")
        if len(content) > max_chars:
            content = content[:max_chars] + "…"
        lines.append(f"[chunk_id={chunk.id}] {content}")
    return "\n\n".join(lines)


def _validate_items(
    items: list[EvalItem],
    allowed_chunk_ids: set[str],
    document_id: str,
) -> list[EvalItem]:
    seen_questions: set[str] = set()
    valid: list[EvalItem] = []

    for item in items:
        question_key = item.question.strip().lower()
        if not question_key or question_key in seen_questions:
            continue
        if not item.expected_answer.strip():
            continue
        if not item.relevant_chunk_ids:
            continue
        if any(cid not in allowed_chunk_ids for cid in item.relevant_chunk_ids):
            continue
        seen_questions.add(question_key)
        payload = item.model_copy()
        payload.document_id = document_id
        valid.append(payload)

    return valid


def _write_markdown(items: list[EvalItem], path: Path) -> None:
    lines = ["# Golden eval dataset", "", f"{len(items)} items generated from fixture.", ""]
    for index, item in enumerate(items, start=1):
        lines.extend(
            [
                f"## {index}. {item.question}",
                f"- Difficulty: {item.difficulty}",
                f"- Expected tools: {', '.join(item.expected_tools)}",
                f"- Chunks: {', '.join(item.relevant_chunk_ids)}",
                f"- Answer: {item.expected_answer}",
                "",
            ]
        )
    path.write_text("\n".join(lines))


async def _generate_items(
    chunks: list[Chunk],
    count: int,
) -> list[EvalItem]:
    prompt = PromptTemplate.from_template(
        """You are building a RAG evaluation dataset for an agency project brief.

Use ONLY the chunk passages below. For each item provide:
- question: natural language question a user might ask
- expected_answer: short gold answer (1-3 sentences) grounded in the chunks
- relevant_chunk_ids: list of chunk_id values that contain the answer
- difficulty: easy | medium | hard
- expected_tools: list containing one of search_documents, keyword_search, list_user_documents
  (use keyword_search for exact terms like dollar amounts or product names)

Generate {count} diverse items covering client name, commercial terms, tech stack,
in-scope features, and out-of-scope guardrails.

Chunks:
{chunks}"""
    )

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.google_api_key,
    ).with_structured_output(EvalGenerationResult)

    try:
        result: EvalGenerationResult = await (prompt | model).ainvoke(
            {"count": count, "chunks": _format_chunks_for_prompt(chunks)}
        )
    except Exception as e:
        raise_llm_http_error(e, action="generate eval dataset")

    return result.items


async def _refine_items(chunks: list[Chunk], items: list[EvalItem]) -> list[EvalItem]:
    prompt = PromptTemplate.from_template(
        """Review eval Q&A items against source chunks. Return indices (0-based) of items
that are clearly grounded, non-ambiguous, and useful for regression testing.
Drop vague or duplicate items.

Chunks:
{chunks}

Items JSON:
{items}"""
    )

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.google_api_key,
    ).with_structured_output(RefineBatch)

    items_json = json.dumps([item.model_dump() for item in items], indent=2)
    try:
        result: RefineBatch = await (prompt | model).ainvoke(
            {
                "chunks": _format_chunks_for_prompt(chunks),
                "items": items_json,
            }
        )
    except Exception as e:
        raise_llm_http_error(e, action="refine eval dataset")

    kept: list[EvalItem] = []
    for index in sorted(set(result.kept_indices)):
        if 0 <= index < len(items):
            kept.append(items[index])
    return kept or items


async def generate_dataset(
    count: int = 10,
    refine: bool = False,
    output_path: Path = GOLDEN_DATASET_PATH,
) -> list[dict[str, Any]]:
    state = load_fixture_state()
    if not state:
        raise RuntimeError("Run python -m eval.seed_fixtures first")

    document_id = UUID(state["document_id"])
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine)

    async with session_factory() as db:
        result = await db.execute(
            select(Chunk)
            .where(Chunk.doc_id == document_id)
            .order_by(Chunk.chunk_index)
        )
        chunks = list(result.scalars().all())
        if not chunks:
            raise RuntimeError("No chunks found for fixture document")

    await engine.dispose()

    allowed_ids = {str(chunk.id) for chunk in chunks}
    raw_items = await _generate_items(chunks, count)
    if refine:
        raw_items = await _refine_items(chunks, raw_items)

    validated = _validate_items(
        raw_items,
        allowed_ids,
        str(document_id),
    )
    if not validated:
        raise RuntimeError("LLM produced no valid eval items")

    payload = [item.model_dump() for item in validated]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))
    _write_markdown(validated, GOLDEN_MARKDOWN_PATH)
    print(f"Wrote {len(validated)} items to {output_path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate golden eval dataset")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--refine", action="store_true")
    parser.add_argument("--output", default=str(GOLDEN_DATASET_PATH))
    args = parser.parse_args()

    asyncio.run(
        generate_dataset(
            count=args.count,
            refine=args.refine,
            output_path=Path(args.output),
        )
    )


if __name__ == "__main__":
    main()
