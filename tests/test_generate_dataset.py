"""Tests for eval dataset validation."""

from eval.generate_dataset import _validate_items
from eval.schemas import EvalItem


def test_validate_items_filters_invalid_chunk_ids_and_duplicates():
    items = [
        EvalItem(
            question="Who is the client?",
            expected_answer="Acme Corp",
            relevant_chunk_ids=["valid-1"],
        ),
        EvalItem(
            question="Who is the client?",
            expected_answer="Duplicate question",
            relevant_chunk_ids=["valid-1"],
        ),
        EvalItem(
            question="What is the liability cap?",
            expected_answer="$50,000",
            relevant_chunk_ids=["missing-id"],
        ),
    ]

    valid = _validate_items(items, {"valid-1"}, "doc-1")
    assert len(valid) == 1
    assert valid[0].document_id == "doc-1"
    assert valid[0].question == "Who is the client?"
