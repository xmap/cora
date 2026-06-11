# Assets

*Equipment BC Assets in the Argonne deployment.*

Argonne National Laboratory is an institution. It is context, not a registered row: there is no Enterprise or Institution kind, so the laboratory is neither an Asset nor a Facility. Facility-envelope scope (site, area) is owned by the Federation `Facility` aggregate, where `FacilityKind` is `{Site, Area}`. A site such as APS is a `Facility` with `FacilityKind = Site`, not an Asset. See the [Argonne index](index.md) for the deployment overview and [Model](../../architecture/model.md) for the aggregate shape.

The Asset tier facet is `Asset.tier`, a closed `AssetTier` StrEnum with three values: `Unit`, `Component`, `Device` (ISA-88 equipment tiers). A ROOT Asset (a beamline) has `parent_id = None` and binds its owning Site through `facility_code`; non-root Assets nest under a parent via `parent_id` and inherit facility scope through that tree. The sites below are facility-envelope, so they are modeled as Facilities, not Asset rows.

| Asset | Tier | Parent |
| --- | --- | --- |

## Pending

The following Argonne sites are facility-envelope and are modeled as `Facility` rows with `FacilityKind = Site`, not as Assets.

| Facility | FacilityKind |
| --- | --- |
| `APS` | `Site` |
| `ATLAS` | `Site` |
| `CNM` | `Site` |
| `ALCF` | `Site` |
