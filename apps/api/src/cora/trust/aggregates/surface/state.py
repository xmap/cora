"""Surface aggregate state, value objects, and domain errors.

A `Surface` is a process-level arrival point — the protocol-bound
socket through which a request entered CORA's process. v1 values:
HTTP, MCP stdio, MCP streamable-http. Distinct from `Conduit` (which
is an ISA-99/IEC-62443 inter-zone topology primitive); v2 memo
locked the decomposition after the v1 conflation was caught by R2C,
see memory/project_conduit_injection_design.md.

Status FSM (`Defined → Versioned → Deprecated`) matches the
Capability / Family / Practice / Method / Plan / Agent template
convention. Lifecycle transitions are future-loadable; v1 ships
genesis only.

Lifecycle timestamps removed (Path C): Surface is a singleton-ish
aggregate (exactly 3 instances — SYSTEM_HTTP / SYSTEM_MCP_STDIO /
SYSTEM_MCP_STREAMABLE_HTTP — all seeded at boot from constants, no
operator-defined Surfaces, no LIST endpoint, no version_surface /
deprecate_surface slices today or planned). The `defined_at` field
was set to boot-time on every
pod restart and the `versioned_at` / `deprecated_at` fields would
always be null in practice — they carried no observable read
value. The cleanest unification is to drop them entirely rather
than build a single-row projection just for timestamp passthrough.
If a future fourth Surface kind ever becomes operator-defined
(triggering a real LIST endpoint), revisit by building a Surface
projection and re-introducing the timestamps there per the
Path C pattern shipped for Method/Plan/Practice/Family/Capability/
Agent.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cora.shared.bounded_text import bounded_name
from cora.trust.aggregates.surface.surface_kind import SurfaceKind

SURFACE_NAME_MAX_LENGTH = 200


class InvalidSurfaceNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Surface name must be 1-{SURFACE_NAME_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class SurfaceAlreadyExistsError(Exception):
    """Attempted to define a surface whose stream already has events."""

    def __init__(self, surface_id: UUID) -> None:
        super().__init__(f"Surface {surface_id} already exists")
        self.surface_id = surface_id


@bounded_name(max_length=SURFACE_NAME_MAX_LENGTH, error_class=InvalidSurfaceNameError)
@dataclass(frozen=True)
class SurfaceName:
    """Display name for a surface. Trimmed; 1-200 chars."""

    value: str


class SurfaceStatus(StrEnum):
    """Lifecycle states. v1 only emits DEFINED; the other values are
    pre-shipped so versioning / deprecation slices can land additively
    later without breaking the state shape.

    Wire values use PascalCase to match every other CORA status enum
    (`AgentStatus.DEFINED = "Defined"`, `CampaignStatus.PLANNED = "Planned"`,
    `CautionStatus.ACTIVE = "Active"`, etc.). The bare-lowercase shape
    that shipped at lock time was an outlier."""

    DEFINED = "Defined"
    VERSIONED = "Versioned"
    DEPRECATED = "Deprecated"


@dataclass(frozen=True)
class Surface:
    """Aggregate root: a process-level arrival surface."""

    id: UUID
    name: SurfaceName
    kind: SurfaceKind
    status: SurfaceStatus
