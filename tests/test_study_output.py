import json

from app.agent.study_output import (
    detect_study_intent,
    format_quiz_answer,
    public_agent_trace,
    resolve_follow_up_question,
    study_answer_from_trace,
)
from app.agent.registry import GENERATE_FLASHCARDS, GENERATE_QUIZ


def test_resolve_follow_up_yes():
    history = [
        {"role": "user", "content": "Create a quiz of 5 questions on the document"},
        {"role": "assistant", "content": "Please confirm"},
    ]
    assert (
        resolve_follow_up_question("yes", history)
        == "Create a quiz of 5 questions on the document"
    )


def test_detect_study_intent_flashcards():
    tool, args = detect_study_intent("Generate 5 flashcards on the document")
    assert tool == GENERATE_FLASHCARDS
    assert args["count"] == 5


def test_detect_study_intent_quiz():
    tool, args = detect_study_intent("Create a quiz of 5 questions on the document")
    assert tool == GENERATE_QUIZ
    assert args["count"] == 5


def test_format_quiz_answer_from_json():
    raw = json.dumps(
        {
            "questions": [
                {
                    "question": "What is critical thinking?",
                    "options": ["A", "B", "C", "D"],
                    "correct_index": 1,
                }
            ]
        }
    )
    answer = format_quiz_answer(raw)
    assert answer is not None
    assert answer.has_answer is True
    assert "Question 1" in answer.answer
    assert "Answer key" in answer.answer


def test_study_answer_prefers_requested_tool():
    flashcards = json.dumps({"cards": [{"front": "Q", "back": "A"}]})
    quiz = json.dumps(
        {
            "questions": [
                {
                    "question": "Quiz Q?",
                    "options": ["1", "2"],
                    "correct_index": 0,
                }
            ]
        }
    )
    trace = [
        {
            "tool": GENERATE_FLASHCARDS,
            "output_summary": flashcards,
            "_full_output": flashcards,
        },
        {
            "tool": GENERATE_QUIZ,
            "output_summary": quiz,
            "_full_output": quiz,
        },
    ]
    flash_answer = study_answer_from_trace(trace, preferred_tool=GENERATE_FLASHCARDS)
    assert flash_answer is not None
    assert "flashcards" in flash_answer.answer.lower()

    quiz_answer = study_answer_from_trace(trace, preferred_tool=GENERATE_QUIZ)
    assert quiz_answer is not None
    assert "Quiz Q?" in quiz_answer.answer


def test_public_agent_trace_strips_internal_fields():
    trace = [{"tool": "generate_quiz", "output_summary": "x", "_full_output": "secret"}]
    public = public_agent_trace(trace)
    assert "_full_output" not in public[0]
