# Deployments

*Pilots earn the abstractions.*

A deployment is a beamline pilot: one instrument where the recipe ladder, BCs, and trust boundaries meet real users. Vertical before horizontal. CORA's domain model only contains what at least one real deployment forced into it; until a beamline demands a shape, the shape stays out.

## Active

| Beamline | Site | Status |
| --- | --- | --- |
| [2-BM](2-bm/index.md) | [APS](aps/index.md), Argonne | Pilot |

## The facility envelope

A beamline is never standalone: it sits inside a facility envelope, the Site that operates it and the institution above that. That context is what a beamline points up into for its clearances, principals, practices, and facility-scope supplies. The envelope is not a separate deployment in its own right, so it lives here as context for the beamline rather than as a peer entry above.

CORA models the three scope levels with three different mechanisms. Facility-envelope scope (institution, site, area) is owned by the Federation `Facility` aggregate, whose `FacilityKind` is `{Site, Area}`. Equipment scope is owned by the `Asset` aggregate, whose `tier` is the closed `AssetTier` StrEnum `{Unit, Component, Device}` (ISA-88 equipment tiers). A root Asset binds its owning Facility through `facility_code`; nested Assets inherit that scope through `parent_id`.

| Scope level | Example | Model |
| --- | --- | --- |
| Institution | [Argonne](argonne/index.md) | Context, not a registered row |
| Site | [APS](aps/index.md) | Federation `Facility`, `FacilityKind = Site` (`facility_code = "aps"`) |
| Beamline | [2-BM](2-bm/index.md) | Equipment `Asset`, root, `tier = Unit`, `facility_code = "aps"` |

An institution such as Argonne is not modeled as an Asset or a Facility; it is context. A site such as APS is a `Facility` with `FacilityKind = Site`. A sector such as Sector 2 is facility-envelope, a `Facility` with `FacilityKind = Area` if modeled, or an organizational grouping, never an Asset row. A beamline such as 2-BM is a root `Asset` with `tier = Unit` bound to its Site via `facility_code`; its sub-systems and devices are nested `Asset`s with `tier = Component` or `tier = Device` under `parent_id`.

Cross-facility vocabulary (Capabilities, Methods) lives in the [Catalog](../catalog/index.md), since it is not bound to any single Site.

When CORA serves a second Site, or federation goes operational across facilities, the envelope graduates from this appendix into its own section. With one Site today, it stays here.
