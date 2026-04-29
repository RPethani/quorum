"""Parallel runner over a batch of `PendingItem`s.

asyncio + `asyncio.to_thread` gives us thread-pool parallelism without
forcing every consumer to be async. Each item is one `invoke()` call;
since items in a single plan are guaranteed to be on different
deliberations (the planner returns at most one per deliberation), the
per-deliberation file lock is only contended in the rare case where
the user edits the same file by hand mid-run — which the lock handles.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

from ..core.context_bundle import summarize_bundle
from ..core.loop import PendingItem
from ..events import ContextLoaded, EventLogger
from ..paths import WorkspacePaths
from .invoker import InvocationRequest, InvocationResult, invoke


async def run_items(
    items: Iterable[PendingItem],
    *,
    paths: WorkspacePaths,
    events: EventLogger | None = None,
    mode: str = "interactive",
    max_concurrent: int = 4,
) -> list[InvocationResult]:
    """Invoke each runnable item concurrently and return the results in order."""
    requests = [
        InvocationRequest(
            handle=item.handle,
            role=item.role,
            move_type=item.move_type,
            deliberation=item.deliberation,
            deliberation_path=item.deliberation_path,
            mode=mode,
        )
        for item in items
    ]

    semaphore = asyncio.Semaphore(max(1, max_concurrent))
    logger = events or EventLogger(paths.events_jsonl)

    # Emit ContextLoaded once per invocation before we hit the agent so
    # the activity feed shows what sources (and how many tokens) the
    # bundle carried. design-doc §1.8 / §10.5.
    for req in requests:
        try:
            tokens, sources = summarize_bundle(paths, req.deliberation)
        except Exception:
            tokens, sources = 0, []
        logger.emit(
            ContextLoaded(
                handle=req.handle.handle,
                role=req.role,
                deliberation_id=req.deliberation.id,
                bundle_tokens_estimated=tokens,
                sources=sources,
            )
        )

    async def _one(req: InvocationRequest) -> InvocationResult:
        async with semaphore:
            return await asyncio.to_thread(invoke, req, paths, events=logger)

    results = await asyncio.gather(*(_one(r) for r in requests))
    return list(results)


def run_items_sync(
    items: Iterable[PendingItem],
    *,
    paths: WorkspacePaths,
    events: EventLogger | None = None,
    mode: str = "interactive",
    max_concurrent: int = 4,
) -> list[InvocationResult]:
    """Synchronous wrapper around `run_items`. Convenient for the CLI."""
    return asyncio.run(
        run_items(
            items,
            paths=paths,
            events=events,
            mode=mode,
            max_concurrent=max_concurrent,
        )
    )
