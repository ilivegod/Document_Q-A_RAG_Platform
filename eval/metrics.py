"""Pure metric helpers for retrieval and agent evaluation."""

from __future__ import annotations

import re


def recall_at_k(retrieved_ids: list[str], relevant: set[str], k: int) -> float:
    top = retrieved_ids[:k]
    hits = sum(1 for cid in top if cid in relevant)
    return 1.0 if hits > 0 else 0.0


def mrr(retrieved_ids: list[str], relevant: set[str]) -> float:
    for rank, cid in enumerate(retrieved_ids, start=1):
        if cid in relevant:
            return 1.0 / rank
    return 0.0


def hit_rate(recalls: list[float]) -> float:
    if not recalls:
        return 0.0
    return sum(recalls) / len(recalls)


def set_overlap_recall(retrieved: set[str], relevant: set[str]) -> float:
    if not relevant:
        return 0.0
    hits = len(retrieved & relevant)
    return hits / len(relevant)


def normalize_tokens(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in tokens if len(t) > 2}


def answer_overlap_score(expected: str, actual: str) -> float:
    """Keyword overlap between expected and actual answer (0–1)."""
    expected_tokens = normalize_tokens(expected)
    if not expected_tokens:
        return 0.0
    actual_tokens = normalize_tokens(actual)
    hits = sum(1 for token in expected_tokens if token in actual_tokens)
    return hits / len(expected_tokens)


def tool_accuracy(expected_tools: list[str], used_tools: list[str]) -> float:
    if not expected_tools:
        return 1.0
    expected = set(expected_tools)
    used = set(used_tools)
    if not used:
        return 0.0
    return len(expected & used) / len(expected)


def aggregate_agent_metrics(rows: list[dict]) -> dict[str, float]:
    if not rows:
        return {}
    n = len(rows)
    return {
        "retrieval_recall": sum(r["retrieval_recall"] for r in rows) / n,
        "has_answer_accuracy": sum(r["has_answer_match"] for r in rows) / n,
        "answer_overlap": sum(r["answer_overlap"] for r in rows) / n,
        "tool_accuracy": sum(r["tool_accuracy"] for r in rows) / n,
        "citation_present_rate": sum(r["citation_present"] for r in rows) / n,
    }
