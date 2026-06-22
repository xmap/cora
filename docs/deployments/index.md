# Deployments

*Pilots earn the abstractions.*

A deployment is a beamline pilot: one instrument where the recipe ladder, BCs, and trust boundaries meet real users. Vertical before horizontal. CORA's domain model only contains what at least one real deployment forced into it; until a beamline demands a shape, the shape stays out.

CORA's operational pilot today is 2-BM, a bending-magnet micro-CT beamline at APS. A second deployment, TomoWise at MAX IV, is in the design phase: its beamline is modelled from the Technical Design Report ahead of construction, so its pages describe an intended shape, not a running instrument. These pages are framed from the beamline outward: the beamline first, then the facility it runs at.

| Beamline | Site | Status |
| --- | --- | --- |
| [2-BM](2-bm/index.md) | [APS](aps/index.md), Argonne | Pilot |
| [TomoWise](tomowise/index.md) | [MAX IV](maxiv/index.md), Lund | In design |

## The facilities

A beamline is never standalone: it sits inside a facility, the Site that operates it and the institution above that. The facility is what a beamline points up into for the clearances, principals, practices, and facility-scope supplies it inherits but does not own. CORA carries one page per Site, [APS](aps/index.md) and [MAX IV](maxiv/index.md), and each beamline links up to its own rather than restating it.

Facility scope and equipment scope are two different aggregates. A Site, and a sector or hutch grouping below it, is a Federation `Facility`, whose `FacilityKind` is `{Site, Area}`. A beamline and the sub-systems under it are Equipment `Asset` rows, whose `tier` is the closed `AssetTier` StrEnum `{Unit, Component, Device}` (ISA-88 equipment tiers). A beamline is a root Asset bound to its Site through `facility_code`; its sub-systems inherit that scope through `parent_id`. Each facility page carries that binding for the Site it describes.

[**APS**](aps/index.md), the Advanced Photon Source, operated by Argonne National Laboratory, is the synchrotron site 2-BM runs at. Its page is the home for the facts a 2-BM experiment inherits but does not own: the Practices (ISA-88 Site Recipes) it runs, the Clearances it must hold, the facility Supplies it draws on, and the people and agents registered facility-wide.

[**MAX IV**](maxiv/index.md), in Lund, Sweden, is the synchrotron site the planned TomoWise beamline will run at, the second Site CORA models. Its page is thin while TomoWise is in design: most facility facts (safety forms, supplies, the operator pool) are carried pending until MAX IV staff confirm them.

The operating institutions, Argonne and Lund University, are context, not modeled rows: there is no Enterprise or Institution kind.

Cross-facility vocabulary (Capabilities, Methods) lives in the [Catalog](../catalog/index.md), since it is not bound to any single Site.
