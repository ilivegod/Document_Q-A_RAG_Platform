import json
import re

from app.agent.registry import GENERATE_FLASHCARDS, GENERATE_QUIZ
from app.services.qa_chain import LLMAnswer

_AFFIRMATIVE = frozenset(
    {
        "yes",
        "y",
        "yeah",
        "yep",
        "sure",
        "ok",
        "okay",
        "please",
        "go ahead",
        "do it",
        "proceed",
        "confirm",
    }
)

_FLASHCARD_RE = re.compile(r"flash\s*card", re.I)
_QUIZ_RE = re.compile(r"\bquiz\b|multiple[- ]choice", re.I)


def resolve_follow_up_question(question: str, chat_history: list[dict] | None) -> str:
    """Map short confirmations back to the prior user request."""
    if not chat_history:
        return question
    normalized = question.strip().lower().rstrip(".!")
    if normalized not in _AFFIRMATIVE:
        return question
    for msg in reversed(chat_history):
        if msg.get("role") == "user":
            return msg["content"]
    return question


def detect_study_intent(question: str) -> tuple[str | None, dict]:
    """Return (tool_name, args) when the user wants flashcards or a quiz."""
    count = 5
    match = re.search(r"\b(\d+)\b", question)
    if match:
        count = max(1, min(int(match.group(1)), 20))

    if _FLASHCARD_RE.search(question):
        return GENERATE_FLASHCARDS, {"topic": question, "count": count}
    if _QUIZ_RE.search(question) or re.search(
        r"\bquestions?\b", question, re.I
    ):
        if _QUIZ_RE.search(question) or re.search(
            r"\b(create|make|generate)\b.*\bquestions?\b", question, re.I
        ):
            return GENERATE_QUIZ, {"topic": question, "count": count}
    return None, {}


def _strip_json_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def format_flashcards_answer(raw: str) -> LLMAnswer | None:
    try:
        data = json.loads(_strip_json_fence(raw))
        cards = data.get("cards", [])
        if not cards:
            return None
        lines = ["Here are your flashcards:\n"]
        for i, card in enumerate(cards, 1):
            front = card.get("front", "").strip()
            back = card.get("back", "").strip()
            lines.append(f"**Card {i}**")
            lines.append(f"- **Front:** {front}")
            lines.append(f"- **Back:** {back}\n")
        return LLMAnswer(has_answer=True, answer="\n".join(lines).strip())
    except (json.JSONDecodeError, TypeError, AttributeError):
        return None


def format_quiz_answer(raw: str) -> LLMAnswer | None:
    try:
        data = json.loads(_strip_json_fence(raw))
        questions = data.get("questions", [])
        if not questions:
            return None
        lines = ["Here is your quiz:\n"]
        answer_key: list[str] = []
        for i, item in enumerate(questions, 1):
            q = item.get("question", "").strip()
            options = item.get("options", [])
            correct_index = int(item.get("correct_index", 0))
            lines.append(f"**Question {i}:** {q}")
            labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            for j, opt in enumerate(options):
                label = labels[j] if j < len(labels) else str(j + 1)
                lines.append(f"  {label}) {opt}")
            if options and 0 <= correct_index < len(options):
                label = labels[correct_index] if correct_index < len(labels) else str(
                    correct_index + 1
                )
                answer_key.append(f"{i}. {label}")
            lines.append("")
        if answer_key:
            lines.append("**Answer key:** " + ", ".join(answer_key))
        return LLMAnswer(has_answer=True, answer="\n".join(lines).strip())
    except (json.JSONDecodeError, TypeError, AttributeError, ValueError):
        return None


def study_answer_from_trace(
    agent_trace: list[dict],
    preferred_tool: str | None = None,
) -> LLMAnswer | None:
    """Prefer the last quiz/flashcard tool output as the user-facing answer."""
    if preferred_tool:
        for step in reversed(agent_trace):
            if step.get("tool") != preferred_tool:
                continue
            answer = _format_study_step(step)
            if answer:
                return answer

    for step in reversed(agent_trace):
        if step.get("tool") not in (GENERATE_QUIZ, GENERATE_FLASHCARDS):
            continue
        answer = _format_study_step(step)
        if answer:
            return answer
    return None


def _format_study_step(step: dict) -> LLMAnswer | None:
    tool = step.get("tool")
    raw = step.get("_full_output") or step.get("output_summary", "")
    if tool == GENERATE_QUIZ:
        return format_quiz_answer(raw)
    if tool == GENERATE_FLASHCARDS:
        return format_flashcards_answer(raw)
    return None


def public_agent_trace(agent_trace: list[dict]) -> list[dict]:
    """Strip internal fields before returning trace to clients."""
    cleaned: list[dict] = []
    for step in agent_trace:
        public = {k: v for k, v in step.items() if not k.startswith("_")}
        cleaned.append(public)
    return cleaned
