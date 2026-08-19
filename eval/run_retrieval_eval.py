"""Retrieval evaluation: recall@k and MRR with per-query breakdown."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Callable, Awaitable
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.services.retrieval import hybrid_search, similarity_search
from eval.metrics import hit_rate, mrr, recall_at_k
from eval.paths import RETRIEVAL_REPORT_PATH
from eval.state import (
    load_dataset,
    load_fixture_state,
    resolve_dataset_path,
    resolve_project_id,
    resolve_user_id,
)


SearchFn = Callable[..., Awaitable[list]]


async def _run_mode(
    *,
    dataset: list[dict[str, Any]],
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID | None,
    k: int,
    search_fn: SearchFn,
    mode: str,
) -> dict[str, Any]:
    recalls: list[float] = []
    mrrs: list[float] = []
    per_query: list[dict[str, Any]] = []

    for item in dataset:
        question = item["question"]
        relevant = set(item.get("relevant_chunk_ids", []))
        doc_id = UUID(item["document_id"]) if item.get("document_id") else None

        chunks = await search_fn(
            question=question,
            db=db,
            user_id=user_id,
            document_id=doc_id,
            project_id=project_id,
            k=k,
        )
        retrieved_ids = [str(c.id) for c in chunks]
        recall = recall_at_k(retrieved_ids, relevant, k)
        rank_score = mrr(retrieved_ids, relevant)
        recalls.append(recall)
        mrrs.append(rank_score)

        per_query.append(
            {
                "question": question,
                "mode": mode,
                "retrieved_ids": retrieved_ids,
                "relevant_chunk_ids": list(relevant),
                "recall_at_k": recall,
                "mrr": rank_score,
                "miss": recall == 0.0,
            }
        )

    n = len(recalls) or 1
    return {
        "mode": mode,
        "queries": len(dataset),
        "k": k,
        "recall_at_k": sum(recalls) / n,
        "mrr": sum(mrrs) / n,
        "hit_rate": hit_rate(recalls),
        "per_query": per_query,
    }


async def run_retrieval_evaluation(
    dataset_path: Path,
    user_id: UUID,
    project_id: UUID | None = None,
    k: int = 5,
    use_hybrid: bool = False,
    compare: bool = False,
) -> dict[str, Any]:
    dataset = load_dataset(dataset_path)
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine)

    async with session_factory() as db:
        if compare:
            vector_result = await _run_mode(
                dataset=dataset,
                db=db,
                user_id=user_id,
                project_id=project_id,
                k=k,
                search_fn=similarity_search,
                mode="vector",
            )
            hybrid_result = await _run_mode(
                dataset=dataset,
                db=db,
                user_id=user_id,
                project_id=project_id,
                k=k,
                search_fn=hybrid_search,
                mode="hybrid",
            )
            result = {
                "dataset": str(dataset_path),
                "compare": True,
                "vector": {k: v for k, v in vector_result.items() if k != "per_query"},
                "hybrid": {k: v for k, v in hybrid_result.items() if k != "per_query"},
                "per_query": {
                    "vector": vector_result["per_query"],
                    "hybrid": hybrid_result["per_query"],
                },
            }
        else:
            search_fn = hybrid_search if use_hybrid else similarity_search
            mode = "hybrid" if use_hybrid else "vector"
            single = await _run_mode(
                dataset=dataset,
                db=db,
                user_id=user_id,
                project_id=project_id,
                k=k,
                search_fn=search_fn,
                mode=mode,
            )
            result = {
                "dataset": str(dataset_path),
                "compare": False,
                **single,
            }

    await engine.dispose()
    return result


def _summary_recall(result: dict[str, Any]) -> float:
    if result.get("compare"):
        return float(result["hybrid"]["recall_at_k"])
    return float(result["recall_at_k"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RAG retrieval evaluation")
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--user-id", default=None)
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--hybrid", action="store_true")
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--min-recall", type=float, default=None)
    parser.add_argument("--output", default=str(RETRIEVAL_REPORT_PATH))
    args = parser.parse_args(argv)

    state = load_fixture_state()
    dataset_path = resolve_dataset_path(args.dataset)
    user_id = resolve_user_id(args.user_id, state)
    project_id = resolve_project_id(args.project_id, state)

    result = asyncio.run(
        run_retrieval_evaluation(
            dataset_path=dataset_path,
            user_id=user_id,
            project_id=project_id,
            k=args.k,
            use_hybrid=args.hybrid,
            compare=args.compare,
        )
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))

    if args.min_recall is not None and _summary_recall(result) < args.min_recall:
        print(
            f"FAIL: recall {_summary_recall(result):.3f} < min {args.min_recall:.3f}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
