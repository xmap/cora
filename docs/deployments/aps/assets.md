# Assets

*Equipment BC Assets bound to the APS Site.*

APS itself is not an Asset: it is a Federation `Facility` with `FacilityKind = Site` (`FacilityCode = "aps"`), declared on the [APS index](index.md). Sectors are facility-envelope scope, an organizational grouping rather than Asset rows; if modeled they are a `Facility` with `FacilityKind = Area` under the Site. In the pilot, beamlines are root Assets (`tier = Unit`, `parent_id = None`) that bind the Site directly via `facility_code`. See [Model](../../architecture/model.md) for the aggregate shape.

| Asset | Tier | facility_code | Hosts |
| --- | --- | --- | --- |
| `2-BM` | `Unit` | `aps` | [2-BM](../2-bm/index.md) |

Sub-systems and devices nested under a beamline are Assets with `tier = Component` or `tier = Device`, linked via `parent_id`. Being non-root, they do not carry `facility_code`; they inherit facility scope through the `parent_id` tree.
