# Model

*The developer's by-kind index: where each CORA aggregate's 8-ID content lives, the XPCS deployment that added the `xpcs` Method and landed the Diffractometer Assembly, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at 8-ID |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## Loose families held for gate-review

8-ID adds a second independent APS beamline (after 4-ID POLAR) to three device classes that recur widely: `TemperatureController`, `Transfocator`, and `PositionMonitor`. All three have since graduated to catalog Families. `TemperatureController` graduated when the parallel Diamond i22/i03/i11 rule-of-three settled the settable-actuator abstraction (`ENV-1`), and it presents the new `Regulator` Role. `Transfocator` graduated as a CRL focusing optic Family, distinct from `Mirror` / `ZonePlate` / `Condenser`: it is bound across several beamlines (APS 4-ID/8-ID/9-id, Diamond i22, NSLS-II chx/smi/ixs, SLAC lcls-mfx), and the cross-facility review settled it as the CRL-specific home rather than a general focusing optic. `PositionMonitor` graduated as its own catalog Family presenting the `Sensor` Role, earned across the wide fleet that shares it (APS 4-ID/8-ID/9-ID, the NSLS-II beamlines, and the imaging and MX beamlines), distinct from the graduated `FluxMonitor` by what it measures: beam position and centroid, not flux or intensity. The still-loose `Diagnostic` family (arrival-time and photon-spectrum monitors) stays loose, a separate abstraction that measures timing and spectrum rather than position; only the per-Asset beam-center calibration and the position-versus-intensity channel split stay open (`DIAG-1`).

| Loose family | Presents (when graduated) | At 4-ID | At 8-ID |
| --- | --- | --- | --- |
| `PositionMonitor` | Sensor | XBPM / Sydor / TetrAMM | Sydor (8-ID-E) + TetrAMM (8-ID-I) |

`Transfocator` and `TemperatureController` were tracked here too and have since graduated to catalog Families. `Transfocator` is the CRL focusing optic Family the two 8-ID-D lens stacks bind (the lens material and lenslet count stay open, `OPT-3`). `TemperatureController` (#350) presents the `Regulator` Role (the LakeShore 336 at 8-ID-E and the Quantum Northwest holders at 8-ID-I bind it). Neither is held for gate-review any longer.

`Magnet` was tracked here too on a single physical beamline (4-ID; `6idb-bits` is a 4-ID fork, see the [4-ID model page](../4-id/model.md#deliberately-not-here-yet)); it has since graduated to a catalog Family on the 4-ID + i10-1 + ID32 rule-of-three (it presents the `Regulator` Role). `Preamplifier` stays loose on that single physical beamline.

## The Diffractometer Assembly (landed)

The `Assembly(Diffractometer)` designed during the catalog-graduation pass is now real, and it **composes the `Goniometer` Family** that landed for I03 MX (#340) rather than re-modelling the sample circles. It is in [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) as a flat assembly presenting the Positioner Role, with slots `goniometer` (Goniometer, `Exactly1`, the sample-orientation circles plus centring), `detector_arm` (RotaryStage, `ZeroOrMore`, spanning 8-ID's nu / delta and 4-ID's detector-arm-less geometries), and `reciprocal_space` (PseudoAxis, whose partition rule resolves the hklpy2 inverse kinematics). The distinction from the Goniometer Family is deliberate: the Goniometer is the integrated single-device sample orienter (the I03 Smargon); the Diffractometer is the larger composed scattering instrument that USES one. The integration scenario [`test_8id_diffractometer_setup.py`](https://github.com/xmap/cora/blob/main/apps/api/tests/integration/scenarios/test_8id_diffractometer_setup.py) materializes it end-to-end against Postgres: it installs the four 8-ID-E constituent Assets (a Goniometer for mu / eta / chi / phi, the nu / delta detector-arm circles, and the reciprocal-space axis), defines the Assembly, and registers a Fixture binding the two detector circles to the `detector_arm` slot. The circle-role confirmation remains `DIFF-1` and the reciprocal-space solver rule is `DIFF-2`; the 4-ID Fixture is the follow-on (the Assembly is shared, the Fixture is per-beamline).

## Deliberately not here yet

- **The UR5 robotic sample changer.** `RobocartUR5` is a user-brought robotic arm; CORA has no sample-changer shape (the same gap the 32-ID projection-microscope changer raised). It is not modelled (`SAMPLE-2`).

- **The softGlue timing graph.** The XPCS exposure timing runs on a softGlueZynq FPGA fabric (`8idMZ1:`); it is modelled coarsely as one `TimingController`, not as its full signal graph (`XPCS-3`).

- **The event-stream acquisition axis (the XPCS execution).** The `xpcs` Method is now in the catalog, but the acquisition primitive that runs it is not: an XPCS Run is a DAQ-owned high-rate frame stream (begin/end a per-frame burst correlated downstream into g2), which CORA's poll-to-Done acquisition bodies (`collect` / `discrete` / `continuous`) cannot execute. 8-ID is the second beamline after LCLS-MFX to hit this, which promoted the event-stream axis to Stage 1 (design-locked, gate-review next; recorded in CORA's design memory). No spine code lands in this pass.

- **The remaining scattering Methods.** Whether small-angle scattering and six-circle diffraction enter CORA's catalog is an owner decision; their Practices render unlinked, pending (`TECH-1`).

- **Full asset-tree scenarios and vendor Models.** Beyond the diffractometer Assembly / Fixture scenario above, no `test_8id_*.py` registers the full 8-ID asset tree (the optics spine, the XPCS endstation), and no vendor Models are bound. Those land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
