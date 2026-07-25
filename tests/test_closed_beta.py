"""Closed beta: unit tests for approval gate and tool unlock."""
import uuid

import pytest
from fastapi import HTTPException

from app.agent.registry import ALL_TOOLS, tools_for_tier
from app.dependencies.auth_guards import require_approved_user
from app.models.user import User, UserTier


def _make_user(is_approved: bool) -> User:
    user = User(
        id=uuid.uuid4(),
        username="test",
        email="test@example.com",
        hashed_password="x",
        is_approved=is_approved,
    )
    return user


def test_require_approved_user_blocks_pending(monkeypatch):
    monkeypatch.setattr("app.dependencies.auth_guards.settings.closed_beta_enabled", True)
    with pytest.raises(HTTPException) as exc:
        require_approved_user(_make_user(is_approved=False))
    assert exc.value.status_code == 403
    assert "pending approval" in exc.value.detail.lower()


def test_require_approved_user_allows_when_beta_off(monkeypatch):
    monkeypatch.setattr("app.dependencies.auth_guards.settings.closed_beta_enabled", False)
    require_approved_user(_make_user(is_approved=False))


def test_require_approved_user_allows_approved(monkeypatch):
    monkeypatch.setattr("app.dependencies.auth_guards.settings.closed_beta_enabled", True)
    require_approved_user(_make_user(is_approved=True))


def test_closed_beta_unlocks_all_tools(monkeypatch):
    monkeypatch.setattr("app.agent.registry.settings.closed_beta_enabled", True)
    assert tools_for_tier(UserTier.FREE) == ALL_TOOLS
