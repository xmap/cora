# Deployments

*Pilots earn the abstractions.*

Vertical before horizontal. CORA's domain model only contains what at least one real deployment forced into it. Until a deployment demands a shape, the shape stays out.

CORA has one pilot today: 2-BM, a bending-magnet micro-CT beamline. These pages are framed from the beamline outward: the pilot first, then the site it runs at.

## The pilot

[**2-BM**](2-bm/index.md) is the deployment. It is a root `Asset` (`tier = Unit`, `parent_id = None`) bound to its Site through `facility_code = "aps"`; its sub-systems and devices nest below as `Asset`s with `tier = Component` or `tier = Device`. The 2-BM page walks the beamline and how a measurement gets done on it.

## The site it runs at

[**APS**](aps/index.md), the Advanced Photon Source, is the synchrotron site 2-BM runs at, operated by Argonne National Laboratory. It is a Federation `Facility` with `FacilityKind = Site` (`facility_code = "aps"`). The APS page is the home for facts the beamline inherits but does not own: the Practices (ISA-88 Site Recipes) it runs, the Clearances it must hold, the facility Supplies it draws on, and the people and agents registered facility-wide. The 2-BM page links up to these rather than restating them.

Argonne, the operating institution, is context, not a modeled row: there is no Enterprise or Institution kind. A sector such as Sector 2 is an organizational grouping, a `Facility` with `FacilityKind = Area` only if it ever needs modeling, never an Asset row.

Cross-facility vocabulary (Capabilities, Methods) lives in the [Catalog](../catalog/index.md), since it is not bound to any single Site.
