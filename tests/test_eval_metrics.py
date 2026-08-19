"""Unit tests for eval metric helpers."""

from eval.metrics import (
    answer_overlap_score,
    mrr,
    recall_at_k,
    set_overlap_recall,
    tool_accuracy,
)


def test_recall_at_k_hit_and_miss():
    relevant = {"a", "b"}
    assert recall_at_k(["x", "a", "y"], relevant, 3) == 1.0
    assert recall_at_k(["x", "y", "z"], relevant, 3) == 0.0


def test_mrr_first_and_later_rank():
    relevant = {"a", "b"}
    assert mrr(["a", "x"], relevant) == 1.0
    assert mrr(["x", "b"], relevant) == 0.5
    assert mrr(["x", "y"], relevant) == 0.0


def test_set_overlap_recall():
    assert set_overlap_recall({"a", "b", "c"}, {"a", "b"}) == 1.0
    assert set_overlap_recall({"a"}, {"a", "b", "c"}) == 0.3333333333333333


def test_answer_overlap_score():
    score = answer_overlap_score(
        "Liability cap is $50,000",
        "The liability cap is fifty thousand dollars ($50,000).",
    )
    assert score >= 0.5


def test_tool_accuracy():
    assert tool_accuracy(["search_documents"], ["search_documents", "list_user_documents"]) == 1.0
    assert tool_accuracy(["keyword_search"], ["search_documents"]) == 0.0
    assert tool_accuracy([], ["search_documents"]) == 1.0
