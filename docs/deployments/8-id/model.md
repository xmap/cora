# Model

*The developer's index into where 8-ID content lives, the catalog graduation this deployment earns, and the record of what is deliberately deferred. First cut.*

8-ID is a descriptor-and-docs scaffold today, reverse-engineered from the beamline's instrument repo: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/8-id/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/8-id/beamline.yaml) | the device walk with bound PVs; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/aps/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/aps/site.yaml) | the APS facility surface; `8-ID` added to its beamline list, with XPCS Practices |
| Extraction provenance | [`research/aps-reverse-engineering/extracted/8id-bits/`](https://github.com/xmap/cora/tree/main/research/aps-reverse-engineering) | the facts report and candidate the descriptor was curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | the three families 8-ID shares with 4-ID are held loose for gate-review (below); 8-ID's other new classes stay loose too |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; XPCS / scattering Methods are not yet coined (TECH-1) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers 8-ID Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## Loose families held for gate-review

8-ID adds a second independent APS beamline (after 4-ID POLAR) to three device classes that recur widely: `TemperatureController`, `Transfocator`, and `BeamPositionMonitor`. The count crosses the promotion threshold, but `main` deliberately holds them loose pending cross-facility abstraction reviews that the parallel Diamond deployments opened: the settable-actuator abstraction (`ENV-1`), the CRL optic's catalog home (`CRL-1`), and the beam-position sensor's fold-vs-promote question against the held `Diagnostic` / `FluxMonitor` families (`DIAG-1` / `FLUX-1`). So they stay loose here too, allowlisted and recorded in the promotion-review register; their naming-r3 review (during the [catalog-graduation pass](https://github.com/xmap/cora/blob/main/research/aps-reverse-engineering/catalog-graduation-decisions.md)) is done, but the abstraction decision is gate-review's, not this PR's.

| Loose family | Presents (when graduated) | At 4-ID | At 8-ID |
| --- | --- | --- | --- |
| `TemperatureController` | Controller | LakeShore 336 / 340 | LakeShore 336 (8-ID-E) + Quantum Northwest holders (8-ID-I) |
| `Transfocator` | Positioner | CRL transfocator | two CRL transfocators (8-ID-D) |
| `BeamPositionMonitor` | Sensor | XBPM / Sydor / TetrAMM | Sydor (8-ID-E) + TetrAMM (8-ID-I) |

`Magnet` and `Preamplifier` are also loose on a single physical beamline (4-ID; `6idb-bits` is a 4-ID fork, see the [4-ID model page](../4-id/model.md#deliberately-not-here-yet)).

## The Diffractometer Assembly (landed)

The `Assembly(Diffractometer)` designed during the catalog-graduation pass is now real, and it **composes the `Goniometer` Family** that landed for I03 MX (#340) rather than re-modelling the sample circles. It is in [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) as a flat assembly presenting the Positioner Role, with slots `goniometer` (Goniometer, `Exactly1`, the sample-orientation circles plus centring), `detector_arm` (RotaryStage, `ZeroOrMore`, spanning 8-ID's nu / delta and 4-ID's detector-arm-less geometries), and `reciprocal_space` (PseudoAxis, whose partition rule resolves the hklpy2 inverse kinematics). The distinction from the Goniometer Family is deliberate: the Goniometer is the integrated single-device sample orienter (the I03 Smargon); the Diffractometer is the larger composed scattering instrument that USES one. The integration scenario [`test_8id_diffractometer_setup.py`](https://github.com/xmap/cora/blob/main/apps/api/tests/integration/scenarios/test_8id_diffractometer_setup.py) materializes it end-to-end against Postgres: it installs the four 8-ID-E constituent Assets (a Goniometer for mu / eta / chi / phi, the nu / delta detector-arm circles, and the reciprocal-space axis), defines the Assembly, and registers a Fixture binding the two detector circles to the `detector_arm` slot. The circle-role confirmation remains `DIFF-1` and the reciprocal-space solver rule is `DIFF-2`; the 4-ID Fixture is the follow-on (the Assembly is shared, the Fixture is per-beamline).

## Deliberately not here yet

- **The UR5 robotic sample changer.** `RobocartUR5` is a user-brought robotic arm; CORA has no sample-changer shape (the same gap the 32-ID projection-microscope changer raised). It is not modelled (`SAMPLE-2`).

- **The softGlue timing graph.** The XPCS exposure timing runs on a softGlueZynq FPGA fabric (`8idMZ1:`); it is modelled coarsely as one `TimingController`, not as its full signal graph (`XPCS-3`).

- **The XPCS / scattering Methods.** Whether XPCS and small-angle scattering enter CORA's catalog is an owner decision; the Practices render unlinked, pending (`TECH-1`).

- **Full asset-tree scenarios and vendor Models.** Beyond the diffractometer Assembly / Fixture scenario above, no `test_8id_*.py` registers the full 8-ID asset tree (the optics spine, the XPCS endstation), and no vendor Models are bound. Those land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
