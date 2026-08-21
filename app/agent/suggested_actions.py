"""Structured action suggestions the user can approve from project chat."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ActionType = Literal[
    "draft_proposal",
    "draft_document",
    "start_proposal_research",  # legacy alias
    "write_company_brief",
]


class SuggestedAction(BaseModel):
    action_type: ActionType
    label: str = Field(max_length=120)
    description: str = Field(max_length=500)
    user_intent: str | None = Field(
        default=None,
        description="Summary of what to write, from the conversation (required for drafts)",
    )


class ProjectAgentAnswer(BaseModel):
    has_answer: bool = Field(
        description="True when you can respond helpfully to the user."
    )
    answer: str = Field(
        description="Conversational reply. Discuss the client, cite documents with [D1] when used."
    )
    suggested_actions: list[SuggestedAction] = Field(
        default_factory=list,
        max_length=2,
        description=(
            "Optional actions the user can approve (e.g. draft a proposal). "
            "Only when they have explained enough and no conflicting workflow is running."
        ),
    )


SUGGESTED_ACTIONS_TOOL = "suggested_actions"


def attach_suggested_actions(
    agent_trace: list[dict],
    actions: list[SuggestedAction],
) -> list[dict]:
    if not actions:
        return agent_trace
    return [
        *agent_trace,
        {
            "tool": SUGGESTED_ACTIONS_TOOL,
            "input": {},
            "output_summary": "",
            "suggested_actions": [a.model_dump() for a in actions],
        },
    ]


def extract_suggested_actions(agent_trace: list[dict] | None) -> list[dict[str, Any]]:
    if not agent_trace:
        return []
    for step in agent_trace:
        if step.get("tool") == SUGGESTED_ACTIONS_TOOL:
            return list(step.get("suggested_actions") or [])
    return []
