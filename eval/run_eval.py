#!/usr/bin/env python3
"""Evaluate retrieval quality: recall@k and MRR.

Usage (from Document_Q&A_RAG_Platform/):
  python -m eval.run_eval --dataset eval/dataset.json --user-id <uuid>

Dataset format (eval/dataset.json):
[
  {
    "question": "What is the liability cap?",
    "relevant_chunk_ids": ["uuid1", "uuid2"],
    "document_id": "optional-doc-uuid"
  }
]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

# Allow running as script from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import settings
from app.services.retrieval import hybrid_search, similarity_search


def recall_at_k(retrieved_ids: list[str], relevant: set[str], k: int) -> float:
    top = retrieved_ids[:k]
    hits = sum(1 for cid in top if cid in relevant)
    return 1.0 if hits > 0 else 0.0


def mrr(retrieved_ids: list[str], relevant: set[str]) -> float:
    for rank, cid in enumerate(retrieved_ids, start=1):
        if cid in relevant:
            return 1.0 / rank
    return 0.0


async def run_evaluation(
    dataset_path: Path,
    user_id: UUID,
    k: int = 5,
    use_hybrid: bool = False,
) -> dict:
    data = json.loads(dataset_path.read_text())
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine)

    recalls = []
    mrrs = []
    search_fn = hybrid_search if use_hybrid else similarity_search

    async with session_factory() as db:
        for item in data:
            question = item["question"]
            relevant = set(item.get("relevant_chunk_ids", []))
            doc_id = UUID(item["document_id"]) if item.get("document_id") else None

            chunks = await search_fn(
                question=question,
                db=db,
                user_id=user_id,
                document_id=doc_id,
                k=k,
            )
            retrieved_ids = [str(c.id) for c in chunks]
            recalls.append(recall_at_k(retrieved_ids, relevant, k))
            mrrs.append(mrr(retrieved_ids, relevant))

    await engine.dispose()

    n = len(recalls) or 1
    return {
        "queries": len(data),
        "k": k,
        "mode": "hybrid" if use_hybrid else "vector",
        "recall_at_k": sum(recalls) / n,
        "mrr": sum(mrrs) / n,
    }


def main():
    parser = argparse.ArgumentParser(description="RAG retrieval evaluation")
    parser.add_argument("--dataset", default="eval/dataset.json")
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--hybrid", action="store_true")
    parser.add_argument("--output", default="eval/results.json")
    args = parser.parse_args()

    result = asyncio.run(
        run_evaluation(
            Path(args.dataset),
            UUID(args.user_id),
            k=args.k,
            use_hybrid=args.hybrid,
        )
    )
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
