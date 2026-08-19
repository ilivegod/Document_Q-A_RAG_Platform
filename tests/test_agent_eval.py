"""Tests for agent eval aggregation."""

from eval.metrics import aggregate_agent_metrics


def test_aggregate_averages_per_query_metrics():
    rows = [
        {
            "retrieval_recall": 1.0,
            "has_answer_match": 1.0,
            "answer_overlap": 0.8,
            "tool_accuracy": 1.0,
            "citation_present": 1.0,
        },
        {
            "retrieval_recall": 0.5,
            "has_answer_match": 0.0,
            "answer_overlap": 0.4,
            "tool_accuracy": 0.5,
            "citation_present": 0.0,
        },
    ]
    agg = aggregate_agent_metrics(rows)
    assert agg["retrieval_recall"] == 0.75
    assert agg["has_answer_accuracy"] == 0.5
    assert abs(agg["answer_overlap"] - 0.6) < 1e-9
    assert agg["tool_accuracy"] == 0.75
    assert agg["citation_present_rate"] == 0.5
