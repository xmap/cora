"""Async context manager that runs the projection worker for the
lifetime of the FastAPI app.

The composition root wraps the FastAPI lifespan body with this
context manager. On entry: spawns the worker as a background task.
On exit: cancels the task and awaits cleanup. Quietly no-ops when
the registry is empty or the kernel has no Postgres pool (i.e.,
`app_env=test` running entirely in-memory).
"""

import asyncio
import contextlib
from collections.abc import AsyncGenerator

from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.projection.bookmark import ensure_bookmarks
from cora.infrastructure.projection.registry import ProjectionRegistry
from cora.infrastructure.projection.wakeup import (
    ListenNotifyWakeup,
    PollOnlyWakeup,
    WakeupSource,
)
from cora.infrastructure.projection.worker import ProjectionWorker

_log = get_logger(__name__)


@contextlib.asynccontextmanager
async def projection_worker_lifespan(
    deps: Kernel,
    registry: ProjectionRegistry,
    settings: Settings,
) -> AsyncGenerator[None]:
    """Spawn the projection worker for the duration of the context.

    No-op cases:
      - The registry is empty (no projections registered yet).
      - The kernel has no Postgres pool (`app_env=test` with in-memory
        adapters; the worker has nothing to read from).

    On normal exit: cancels the worker task, waits for it to finish
    (suppressing `CancelledError`), closes the wake-up source.
    """
    if registry.is_empty() or deps.pool is None:
        _log.info(
            "projection_worker.skipped",
            reason="empty registry" if registry.is_empty() else "no pool",
        )
        yield
        return

    # Ensure a bookmark row exists for every registered subscriber before the
    # worker starts. Projections already have theirs (seeded by their migration);
    # this creates the otherwise-missing rows for Reactions (side-effecting
    # subscribers own no proj_* table, hence no migration, hence no seed). Without
    # it a Reaction's first advance raises MissingBookmarkError forever inside the
    # worker's backoff loop and it never fires. Idempotent (ON CONFLICT DO NOTHING).
    await ensure_bookmarks(deps.pool, registry.names())

    wakeup: WakeupSource = (
        ListenNotifyWakeup(deps.pool) if settings.projection_use_listen_notify else PollOnlyWakeup()
    )
    worker = ProjectionWorker(
        deps.pool,
        registry,
        wakeup,
        poll_interval_seconds=settings.projection_poll_interval_seconds,
    )
    _log.info(
        "projection_worker.started",
        projections=sorted(registry.names()),
        wakeup=type(wakeup).__name__,
        poll_interval_seconds=settings.projection_poll_interval_seconds,
    )
    task = asyncio.create_task(worker.run(), name="projection-worker")
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await wakeup.close()
        _log.info("projection_worker.stopped")


__all__ = ["projection_worker_lifespan"]
