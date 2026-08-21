"""End-to-end agent evaluation using run_agent."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agent.context import AgentContext
from app.agent.orchestrator import run_agent
from app.config import settings
from app.models.user import UserTier
from eval.metrics import (
    answer_overlap_score,
    aggregate_agent_metrics,
    set_overlap_recall,
    tool_accuracy,
)
from eval.paths import REPORT_PATH
from eval.state import (
    load_dataset,
    load_fixture_state,
    resolve_dataset_path,
    resolve_project_id,
    resolve_user_id,
)


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, float]:
    return aggregate_agent_metrics(rows)


async def run_agent_evaluation(
    dataset_path: Path,
    user_id: UUID,
    project_id: UUID,
    document_id: UUID,
) -> dict[str, Any]:
    dataset = load_dataset(dataset_path)
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine)

    rows: list[dict[str, Any]] = []

    async with session_factory() as db:
        for item in dataset:
            question = item["question"]
            relevant = set(item.get("relevant_chunk_ids", []))
            expected_answer = item.get("expected_answer", "")
            expected_tools = item.get("expected_tools", ["search_documents"])
            expect_has_answer = bool(item.get("expect_has_answer", True))
            item_doc_id = item.get("document_id") or str(document_id)

            ctx = AgentContext(
                db=db,
                user_id=user_id,
                document_id=UUID(item_doc_id),
                project_id=project_id,
            )
            answer, trace, chunks, _web, _actions = await run_agent(
                question,
                ctx,
                UserTier.PRO,
                chat_history=None,
            )
            retrieved_ids = {str(c.id) for c in chunks}
            used_tools = [step.get("tool", "") for step in trace]

            retrieval_recall = set_overlap_recall(retrieved_ids, relevant)
            has_answer_match = 1.0 if answer.has_answer == expect_has_answer else 0.0
            overlap = answer_overlap_score(expected_answer, answer.answer)
            tools_score = tool_accuracy(expected_tools, used_tools)
            citation_present = (
                1.0
                if answer.has_answer
                and chunks
                and "[D" in answer.answer
                else 0.0
            )

            rows.append(
                {
                    "question": question,
                    "expected_answer": expected_answer,
                    "actual_answer": answer.answer,
                    "has_answer": answer.has_answer,
                    "expect_has_answer": expect_has_answer,
                    "retrieval_recall": retrieval_recall,
                    "has_answer_match": has_answer_match,
                    "answer_overlap": overlap,
                    "tool_accuracy": tools_score,
                    "citation_present": citation_present,
                    "used_tools": used_tools,
                    "retrieved_chunk_ids": sorted(retrieved_ids),
                    "relevant_chunk_ids": sorted(relevant),
                }
            )

    await engine.dispose()

    return {
        "dataset": str(dataset_path),
        "queries": len(rows),
        "aggregate": _aggregate(rows),
        "per_query": rows,
    }


def _print_summary(result: dict[str, Any]) -> None:
    agg = result["aggregate"]
    print("Agent eval summary:")
    for key, value in agg.items():
        print(f"  {key}: {value:.3f}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="End-to-end agent evaluation")
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--user-id", default=None)
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--document-id", default=None)
    parser.add_argument("--output", default=str(REPORT_PATH))
    args = parser.parse_args(argv)

    state = load_fixture_state()
    if not state:
        print("Run python -m eval.seed_fixtures first", file=sys.stderr)
        return 1

    dataset_path = resolve_dataset_path(args.dataset)
    user_id = resolve_user_id(args.user_id, state)
    project_id = resolve_project_id(args.project_id, state)
    if project_id is None:
        print("project_id required", file=sys.stderr)
        return 1

    document_id = UUID(args.document_id or state["document_id"])

    result = asyncio.run(
        run_agent_evaluation(
            dataset_path=dataset_path,
            user_id=user_id,
            project_id=project_id,
            document_id=document_id,
        )
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2))
    _print_summary(result)
    print(json.dumps(result["aggregate"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
