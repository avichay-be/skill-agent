"""Tests for timezone-aware datetime usage (Python 3.12+ deprecation fix).

This module verifies that all datetime objects in the codebase are timezone-aware,
replacing deprecated datetime.utcnow() with datetime.now(timezone.utc).
"""

from datetime import datetime, timezone


def test_executor_metadata_started_at_is_timezone_aware():
    """Test that ExecutionMetadata started_at uses timezone-aware datetime."""
    from app.models.execution import ExecutionMetadata

    metadata = ExecutionMetadata()
    assert metadata.started_at is not None
    assert metadata.started_at.tzinfo is not None, (
        "started_at should be timezone-aware (use datetime.now(timezone.utc))"
    )
    assert metadata.started_at.tzinfo == timezone.utc, "started_at should use UTC timezone"


def test_skill_graph_state_started_at_is_timezone_aware():
    """Test that SkillGraphState started_at uses timezone-aware datetime."""
    from app.services.graph.state import SkillGraphState

    state = SkillGraphState(
        document="test document",
        schema_id="test_schema",
        execution_id="test_execution_id",
    )
    assert state.started_at is not None
    assert state.started_at.tzinfo is not None, (
        "started_at should be timezone-aware (use datetime.now(timezone.utc))"
    )
    assert state.started_at.tzinfo == timezone.utc, "started_at should use UTC timezone"


def test_datetime_now_utc_returns_timezone_aware():
    """Verify datetime.now(timezone.utc) produces timezone-aware datetimes."""
    now = datetime.now(timezone.utc)
    assert now.tzinfo is not None
    assert now.tzinfo == timezone.utc


def test_datetime_utcnow_is_naive():
    """Document that datetime.utcnow() is naive (this is why we must avoid it)."""
    # This test documents the problem - utcnow() returns naive datetime
    now = datetime.utcnow()
    assert now.tzinfo is None, "datetime.utcnow() returns naive datetime (no timezone)"
