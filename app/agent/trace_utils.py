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


def public_agent_trace(agent_trace: list[dict]) -> list[dict]:
    """Strip internal fields before returning trace to clients."""
    cleaned: list[dict] = []
    for step in agent_trace:
        public = {k: v for k, v in step.items() if not k.startswith("_")}
        cleaned.append(public)
    return cleaned
