# Deployments

*Pilots earn the abstractions.*

A deployment is a beamline pilot: one instrument where the recipe ladder, BCs, and trust boundaries meet real users. Vertical before horizontal. CORA's domain model only contains what at least one real deployment forced into it; until a beamline demands a shape, the shape stays out.

CORA's operational pilot today is 2-BM, a bending-magnet micro-CT beamline at APS. A second deployment, TomoWise at MAX IV, is in the design phase: its beamline is modelled from the Technical Design Report ahead of construction, so its pages describe an intended shape, not a running instrument. These pages are framed from the beamline outward: the beamline first, then the site it runs at.

| Beamline | Site | Status |
| --- | --- | --- |
| [2-BM](2-bm/index.md) | [APS](aps/index.md), Argonne | Pilot |
| [TomoWise](tomowise/index.md) | [MAX IV](maxiv/index.md), Lund | In design |

## The facility envelope

A beamline is never standalone: it sits inside a facility envelope, the Site that operates it and the institution above that. That context is what a beamline points up into for its clearances, principals, practices, and facility-scope supplies. The envelope is not a separate deployment in its own right, so it lives here as context for the beamline rather than as a peer entry above.

CORA models the three scope levels with three different mechanisms. Facility-envelope scope (institution, site, area) is owned by the Federation `Facility` aggregate, whose `FacilityKind` is `{Site, Area}`. Equipment scope is owned by the `Asset` aggregate, whose `tier` is the closed `AssetTier` StrEnum `{Unit, Component, Device}` (ISA-88 equipment tiers). A root Asset binds its owning Facility through `facility_code`; nested Assets inherit that scope through `parent_id`.

| Scope level | Example | Model |
| --- | --- | --- |
| Institution | Argonne; Lund University | Context, not a registered row |
| Site | [APS](aps/index.md); [MAX IV](maxiv/index.md) | Federation `Facility`, `FacilityKind = Site` (`facility_code = "aps"` / `"maxiv"`) |
| Beamline | [2-BM](2-bm/index.md) at APS; [TomoWise](tomowise/index.md) at MAX IV | Equipment `Asset`, root, `tier = Unit`, bound by `facility_code` |

## The sites they run at

[**APS**](aps/index.md), the Advanced Photon Source, is the synchrotron site 2-BM runs at, operated by Argonne National Laboratory. It is a Federation `Facility` with `FacilityKind = Site` (`facility_code = "aps"`). The APS page is the home for facts the beamline inherits but does not own: the Practices (ISA-88 Site Recipes) it runs, the Clearances it must hold, the facility Supplies it draws on, and the people and agents registered facility-wide. The 2-BM page links up to these rather than restating them.

[**MAX IV**](maxiv/index.md), in Lund, Sweden, is the synchrotron site the planned TomoWise beamline will run at, the second Site CORA models. It is a Federation `Facility` with `FacilityKind = Site` (`facility_code = "maxiv"`). Its page is thin while TomoWise is in design: most facility facts (safety forms, supplies, the operator pool) are carried pending until MAX IV staff confirm them.

The operating institutions, Argonne and Lund University, are context, not modeled rows: there is no Enterprise or Institution kind. A sector or hutch grouping is a `Facility` with `FacilityKind = Area` only if it ever needs modeling, never an Asset row.

Cross-facility vocabulary (Capabilities, Methods) lives in the [Catalog](../catalog/index.md), since it is not bound to any single Site.

A second Site is what graduates the facility envelope from a single appendix into its own area: the facility pages now carry one page per Site, [APS](aps/index.md) and [MAX IV](maxiv/index.md), with each beamline linking up to its own.
