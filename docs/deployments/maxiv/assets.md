# Assets

*Equipment BC Assets bound to the MAX IV Site.*

MAX IV itself is not an Asset: it is a Federation `Facility` with `FacilityKind = Site` (`FacilityCode = "maxiv"`), declared on the [MAX IV index](index.md). In the pilot pattern, beamlines are root Assets (`tier = Unit`, `parent_id = None`) that bind the Site directly via `facility_code`. See [Model](../../architecture/model.md) for the aggregate shape.

| Asset | Tier | facility_code | Hosts |
| --- | --- | --- | --- |
| `TomoWISE` | `Unit` | `maxiv` | [TomoWise](../tomowise/index.md) |

Sub-systems and devices nested under the beamline are Assets with `tier = Component` or `tier = Device`, linked via `parent_id`. Being non-root, they do not carry `facility_code`; they inherit facility scope through the `parent_id` tree.

TomoWISE is in the design phase: the asset tree above is the planned shape, not a registered inventory.
