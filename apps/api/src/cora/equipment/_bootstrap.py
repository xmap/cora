"""BC-level bootstrap re-exports and startup-time configuration checks.

Preserves the import path
`cora.equipment._bootstrap.SYSTEM_PRINCIPAL_ID` used by Equipment's
MCP tools. The constant itself lives at
`cora.infrastructure.routing.SYSTEM_PRINCIPAL_ID` since the
post-Phase-3 cleanup hoisted both BCs' identical fallback constants
to one canonical home.

`check_pidinst_landing_page_template` is called from
`wire_equipment` at startup. Failing here keeps the PIDINST view
assembler free of per-request guards: if the template is missing,
the process never finishes booting and the route is unreachable. See
L12 + L17 of project_asset_persistent_id_design.

`bootstrap_equipment` seeds the 4 SEED_ROLES at lifespan startup.
Without it the 3D `bind_plan_role` role_kind path and the 3E
`update_capability_suggested_roles` handler both raise
`RoleNotFoundError` until operators manually issue 4 `POST /roles`
calls. Mirrors the `bootstrap_federation` shape
(ConcurrencyError-as-already-seeded) and is called from
`api/main.py` lifespan after `bootstrap_federation`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.equipment.aggregates.role import (
    SEED_ROLES,
    RoleDefined,
    event_type_name,
    to_payload,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports.event_store import ConcurrencyError
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

if TYPE_CHECKING:
    from cora.infrastructure.config import Settings
    from cora.infrastructure.kernel import Kernel

_ROLE_STREAM_TYPE = "Role"
_COMMAND_NAME = "bootstrap_equipment"

_log = get_logger(__name__)


def check_pidinst_landing_page_template(settings: Settings) -> None:
    """Refuse to boot when the PIDINST landing-page template is empty.

    The PIDINST read route formats `landing_page_template` with the
    target asset's id to produce PIDINST v1.0 Property 3
    `landingPage`. An empty template would silently produce an empty
    landing page string and the serializer's `LandingPageMissingError`
    would fire on every request instead of at startup. Raising
    here makes the misconfiguration visible at boot.
    """
    if not settings.landing_page_template or not settings.landing_page_template.strip():
        raise RuntimeError(
            "Settings.landing_page_template must be non-empty: the PIDINST read "
            "route formats it with the target asset_id to produce the landing-page "
            "URL. Set LANDING_PAGE_TEMPLATE in the environment."
        )


async def bootstrap_equipment(kernel: Kernel) -> None:
    """Seed the 4 closed-core Roles into the event store (idempotent).

    Iterates `SEED_ROLES` and direct-appends one `RoleDefined` event
    per Role at `stream_id = role.id` (the deterministic uuid5).
    `ConcurrencyError` on `expected_version=0` means the seed is
    already present; we log and continue.

    Safe to call on every app boot. LOAD-BEARING ORDER: must run
    BEFORE any handler that resolves a Role via `RoleLookup`
    (`bind_plan_role` role_kind path, `update_capability_suggested_roles`).
    """
    now = kernel.clock.now()
    correlation_id = kernel.id_generator.new_id()

    for role in SEED_ROLES:
        defined = RoleDefined(
            role_id=role.id,
            name=role.name.value,
            docstring=role.docstring,
            required_affordances=role.required_affordances,
            optional_affordances=role.optional_affordances,
            produces=role.produces,
            consumes=role.consumes,
            occurred_at=now,
        )
        new_event = to_new_event(
            event_type=event_type_name(defined),
            payload=to_payload(defined),
            occurred_at=now,
            event_id=kernel.id_generator.new_id(),
            command_name=_COMMAND_NAME,
            correlation_id=correlation_id,
            causation_id=None,
            principal_id=SYSTEM_PRINCIPAL_ID,
        )

        try:
            await kernel.event_store.append(
                stream_type=_ROLE_STREAM_TYPE,
                stream_id=role.id,
                expected_version=0,
                events=[new_event],
            )
        except ConcurrencyError:
            _log.info(
                "role_seed.already_present",
                role_id=str(role.id),
                role_name=role.name.value,
            )
            continue

        _log.info(
            "role_seed.created",
            role_id=str(role.id),
            role_name=role.name.value,
        )


__all__ = [
    "SYSTEM_PRINCIPAL_ID",
    "bootstrap_equipment",
    "check_pidinst_landing_page_template",
]
