# Facilities

A beamline is never standalone: it sits inside a facility, the Site that operates it and the institution above that. The facility is what a beamline points up into for the clearances, principals, practices, and facility-scope supplies it inherits but does not own. CORA carries one page per Site, [APS](../aps/index.md) and [MAX IV](../maxiv/index.md), and each beamline links up to its own rather than restating it.

Facility scope and equipment scope are two different aggregates. A Site, and a sector or hutch grouping below it, is a Federation `Facility`, whose `FacilityKind` is `{Site, Area}`. A beamline and the sub-systems under it are Equipment `Asset` rows, whose `tier` is the closed `AssetTier` StrEnum `{Unit, Component, Device}` (ISA-88 equipment tiers). A beamline is a root Asset bound to its Site through `facility_code`; its sub-systems inherit that scope through `parent_id`. Each facility page carries that binding for the Site it describes.

[**APS**](../aps/index.md), the Advanced Photon Source, operated by Argonne National Laboratory, is the synchrotron site 2-BM runs at, and the planned 7-BM beamline (Sector 7, in design) as well. Its page is the home for the facts a beamline experiment inherits but does not own: the Practices (ISA-88 Site Recipes) it runs, the Clearances it must hold, the facility Supplies it draws on, and the people and agents registered facility-wide. Because 7-BM runs at the same Site, it reuses this envelope rather than creating a new one.

[**MAX IV**](../maxiv/index.md), in Lund, Sweden, is the synchrotron site the planned TomoWise beamline will run at, the second Site CORA models. Its page is thin while TomoWise is in design: most facility facts (safety forms, supplies, the operator pool) are carried pending until MAX IV staff confirm them.

The operating institutions, Argonne and Lund University, are context, not modeled rows: there is no Enterprise or Institution kind.

Cross-facility vocabulary (Capabilities, Methods) lives in the [Catalog](../../catalog/index.md), since it is not bound to any single Site.
