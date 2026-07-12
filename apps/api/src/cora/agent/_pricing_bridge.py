"""Catalog pricing bridge: feeds the observability cost overlay.

The LanguageModel catalog is the governance home of pricing; the
observability module's static `PRICING` table is the fallback and the
day-1 content. This bridge closes the gap at startup: it collects
every Approved catalog entry's token pricing and hands the whole
mapping to `set_pricing_overlay` in one atomic replace, so
`compute_cost_usd` and the pre-estimate ceiling meter the price the
facility actually governs.

Pricing has ONE home, the aggregate: `cost_basis` is deliberately not
projected (a rate column on the read model would be a second pricing
home to drift), so the bridge queries the projection only for the
Approved ids and folds each stream via `load_language_model`. The
entry count is config-shaped (a handful of models), so the per-id
fold is cheap and runs once per boot.

GpuHourPricing entries are skipped: the overlay feeds per-token cost
math only, and GPU-hour rates feed the future allocation arc.
"""

from __future__ import annotations

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
from typing import TYPE_CHECKING

from cora.agent.aggregates.language_model import (
    LanguageModelStatus,
    TokenPricing,
    load_language_model,
)
from cora.infrastructure.logging import get_logger
from cora.infrastructure.observability.gen_ai import ModelPricing, set_pricing_overlay

if TYPE_CHECKING:
    import asyncpg

    from cora.infrastructure.ports import EventStore

_log = get_logger(__name__)

# ASC order makes duplicate identities deterministic: later rows
# overwrite earlier ones in the mapping, so the newest Approved entry
# wins, mirroring PostgresLanguageModelLookup's newest-wins posture
# (its query reads the same ordering DESC with LIMIT 1).
_APPROVED_IDS_SQL = """
SELECT language_model_id
FROM proj_agent_language_model_summary
WHERE status = 'Approved'
ORDER BY created_at ASC, language_model_id ASC
"""


def to_model_pricing(cost_basis: TokenPricing) -> ModelPricing:
    """Map a catalog entry's token pricing onto the observability shape.

    The single mapping site: the bridge installs through it and the
    seed day-one-equality test exercises it, so a field swap here
    cannot pass one and fool the other.
    """
    return ModelPricing(
        input_per_mtok=cost_basis.input_per_mtok,
        output_per_mtok=cost_basis.output_per_mtok,
        cache_write_per_mtok=cost_basis.cache_write_per_mtok,
        cache_read_per_mtok=cost_basis.cache_read_per_mtok,
    )


async def refresh_language_model_pricing(*, pool: asyncpg.Pool, event_store: EventStore) -> int:
    """Rebuild the observability pricing overlay from the catalog.

    Loads every Approved entry's aggregate, maps the TokenPricing ones
    onto `ModelPricing` keyed by the entry's `(provider, model)`
    identity, and replaces the overlay wholesale (so an entry that
    lost approval since the last refresh falls back to the static
    table). Returns the number of overlay entries installed.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(_APPROVED_IDS_SQL)

    overlay: dict[tuple[str, str], ModelPricing] = {}
    gpu_hour_skipped = 0
    for row in rows:
        entry = await load_language_model(event_store, row["language_model_id"])
        if entry is None or entry.status is not LanguageModelStatus.APPROVED:
            # The projection filtered on Approved, but the AGGREGATE is
            # authoritative: the future in-process refresh subscriber will
            # run in projection-lag windows where a stale-Approved row
            # folds to a withdrawn entry, and a withdrawn price must
            # never be installed.
            continue
        if not isinstance(entry.cost_basis, TokenPricing):
            gpu_hour_skipped += 1
            continue
        overlay[(entry.model_ref.provider, entry.model_ref.model)] = to_model_pricing(
            entry.cost_basis
        )

    set_pricing_overlay(overlay)
    _log.info(
        "pricing_bridge.refreshed",
        overlay_entries=len(overlay),
        approved_entries=len(rows),
        gpu_hour_skipped=gpu_hour_skipped,
    )
    return len(overlay)


__all__ = ["refresh_language_model_pricing"]
