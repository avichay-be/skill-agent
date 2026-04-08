"""Tests for GraphExecutor initialization and configuration."""

import pytest

from app.services.graph_executor import GraphExecutor


class TestGraphExecutorInit:
    """Tests for GraphExecutor initialization."""

    def test_executor_initializes(self) -> None:
        executor = GraphExecutor()
        assert executor is not None
        assert executor.settings is not None

    def test_executor_uses_provided_settings(self) -> None:
        from types import SimpleNamespace

        settings = SimpleNamespace(
            checkpoint_backend="memory",
            checkpoint_db_path="./test.db",
        )
        executor = GraphExecutor(settings=settings)
        assert executor.settings.checkpoint_backend == "memory"


class TestGraphExecutorCheckpointer:
    """Tests for checkpointer context manager."""

    @pytest.mark.asyncio
    async def test_memory_checkpointer(self) -> None:
        from types import SimpleNamespace

        settings = SimpleNamespace(
            checkpoint_backend="memory",
            checkpoint_db_path="./data/test.db",
        )
        executor = GraphExecutor(settings=settings)
        async with executor._checkpointer_context() as cp:
            assert cp is not None

    @pytest.mark.asyncio
    async def test_sqlite_checkpointer_creates_dir(self, tmp_path: object) -> None:
        from types import SimpleNamespace

        db_path = f"{tmp_path}/subdir/test.db"
        settings = SimpleNamespace(
            checkpoint_backend="sqlite",
            checkpoint_db_path=db_path,
        )
        executor = GraphExecutor(settings=settings)
        async with executor._checkpointer_context() as cp:
            assert cp is not None
