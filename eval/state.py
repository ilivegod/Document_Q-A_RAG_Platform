"""Load and save eval fixture state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from eval.paths import (
    DEFAULT_DATASET_PATH,
    FIXTURE_STATE_PATH,
    GOLDEN_DATASET_PATH,
)


def load_fixture_state(path: Path = FIXTURE_STATE_PATH) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_fixture_state(state: dict[str, Any], path: Path = FIXTURE_STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))


def resolve_dataset_path(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit)
    if GOLDEN_DATASET_PATH.exists():
        return GOLDEN_DATASET_PATH
    return DEFAULT_DATASET_PATH


def load_dataset(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text())


def resolve_user_id(
    explicit: str | None,
    state: dict[str, Any] | None,
) -> UUID:
    if explicit:
        return UUID(explicit)
    if state and state.get("user_id"):
        return UUID(state["user_id"])
    raise ValueError("user_id required (pass --user-id or run eval.seed_fixtures first)")


def resolve_project_id(
    explicit: str | None,
    state: dict[str, Any] | None,
) -> UUID | None:
    if explicit:
        return UUID(explicit)
    if state and state.get("project_id"):
        return UUID(state["project_id"])
    return None
