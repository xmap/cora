"""Typed dataclasses for the AssetIntegrationView bundle.

v1 of the MTP-style read-model bundle. Handler returns the
domain-typed `AssetIntegrationView` directly (not a JSON DTO); the
route + MCP tool layers serialize independently. See
[[project-asset-integration-view-design]] for the locked shape +
the rationale for keeping these as domain types rather than DTOs.

Bundle scope (CLOSED at v1):
  - Asset core (id, name, tier, lifecycle, condition, parent_id)
  - families: list of (family_id, name, affordances)
  - ports: list of (name, direction, signal_type)
  - settings: raw dict[str, Any]
  - active_cautions: list of (caution_id, category, severity, text)
  - applicable_capabilities: list of (capability_id, code, name, status)
  - incomplete: bool — TRUE if any Family in Asset.family_ids failed to load
    (mirrors promote_dataset peer-load tolerance per
    [[project-dataset-lineage-design]])

Conduit options DROPPED from v1 — no Asset-Conduit linkage exists in
CORA today.

HMI / alarms / safety / time-series-history out of scope (Q1 anti-hook
#1: over-bundling drift; see [[project-mtp-integration-manifest-research]]).
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class FamilyView:
    """One Family the Asset belongs to: id + name + affordances set.

    `affordances` is a frozenset of Affordance enum string values
    (matches the closed enum at `cora.equipment.aggregates.family.affordance`).
    """

    family_id: UUID
    name: str
    affordances: frozenset[str]


@dataclass(frozen=True)
class PortView:
    """One typed port the Asset exposes (5h): name + direction + signal_type."""

    name: str
    direction: str
    signal_type: str


@dataclass(frozen=True)
class CautionView:
    """One active Caution targeting this Asset (Caution BC 11b).

    `text` is the operator-authored Caution body; `severity` is the
    Z535-downshifted enum string (Notice | Caution | Warning); `category`
    is one of the 6 closed Caution categories.
    """

    caution_id: UUID
    category: str
    severity: str
    text: str


@dataclass(frozen=True)
class CapabilityView:
    """One Capability whose required_affordances are covered by the Asset's
    combined Family affordances (Recipe BC).

    Filtered to status IN ('Defined', 'Versioned') — Deprecated
    Capabilities EXCLUDED per the design lock.
    """

    capability_id: UUID
    code: str
    name: str
    status: str


@dataclass(frozen=True)
class AssetIntegrationView:
    """The composed integration bundle for one Asset.

    Returned by the `get_asset_integration_view` handler. v1 is built
    via read-time composition (no projection table, no subscribers);
    v2 promotion to a denormalized projection lands on rule-of-three
    trigger per the design memo.
    """

    asset_id: UUID
    name: str
    tier: str
    lifecycle: str
    condition: str
    parent_id: UUID | None
    families: tuple[FamilyView, ...] = field(default_factory=tuple)
    ports: tuple[PortView, ...] = field(default_factory=tuple)
    settings: dict[str, Any] = field(default_factory=dict[str, Any])
    active_cautions: tuple[CautionView, ...] = field(default_factory=tuple)
    applicable_capabilities: tuple[CapabilityView, ...] = field(default_factory=tuple)
    incomplete: bool = False
