# Deployments

*Pilots earn the abstractions.*

Vertical before horizontal. CORA's domain model only contains what at least one real deployment forced into it. A deployment is a real-world scope (an institution, a site, or an instrument) where the recipe ladder, BCs, and trust boundaries meet actual users. Until a deployment demands a shape, the shape stays out.

## Active

Deployments span two complementary models. Facility-envelope scope (institution, site, area) is owned by the Federation `Facility` aggregate, whose `FacilityKind` is `{Site, Area}`. Equipment scope is owned by the `Asset` aggregate, whose `tier` is the closed `AssetTier` StrEnum `{Unit, Component, Device}` (ISA-88 equipment tiers). A root Asset binds its owning Facility through `facility_code`; nested Assets inherit that scope through `parent_id`.

| Deployment | Model | Scope |
| --- | --- | --- |
| [Argonne](argonne/index.md) | Institution | Context, not a registered row |
| [APS](aps/index.md) | Facility | `FacilityKind = Site` (`facility_code = "aps"`) |
| [2-BM](2-bm/index.md) | Asset | Root, `tier = Unit`, `facility_code = "aps"` |

An institution such as Argonne is not modeled as an Asset or a Facility; it is context. A site such as APS is a `Facility` with `FacilityKind = Site`. A sector such as Sector 2 is facility-envelope, a `Facility` with `FacilityKind = Area` if modeled, or an organizational grouping, never an Asset row. A beamline such as 2-BM is a root `Asset` with `tier = Unit` bound to its Site via `facility_code`; its sub-systems and devices are nested `Asset`s with `tier = Component` or `tier = Device` under `parent_id`.

Cross-facility vocabulary (Capabilities, Methods) lives in the [Catalog](../catalog/index.md), since it is not bound to any single Site.
