# Argonne

*Institution context for the Sites it operates.*

Argonne National Laboratory is the operating institution. It is not modeled as an Asset or a Facility (there is no Enterprise or Institution kind); it is context for the Sites that hang off it. Each Site it runs is a Federation `Facility` with `FacilityKind = Site`.

| Property | Value |
| --- | --- |
| Institution | `Argonne` (context, not a registered row) |
| Active site | [APS](../aps/index.md) |

## Assets and sites

Argonne holds no Asset rows of its own. Equipment scope (the `Asset` aggregate, with `tier` in `{Unit, Component, Device}`) hangs off a Site through `facility_code` and `parent_id`, never off the institution. See [Model](../../architecture/model.md) for the aggregate shape.

The Sites this institution operates are facility-envelope scope, modeled as `Facility` rows with `FacilityKind = Site`, not as Assets:

| Facility | FacilityKind | Status |
| --- | --- | --- |
| `APS` | `Site` | Active |
| `ATLAS` | `Site` | Pending |
| `CNM` | `Site` | Pending |
| `ALCF` | `Site` | Pending |
