# Model

*The developer's by-kind index: where each CORA aggregate's ID32 content lives, the graduations it earns, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at ID32 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (the polarization PseudoAxis) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What makes ID32 new

ID32 is two things the fleet has not had: a new Site and a new controls house-style. It is CORA's **seventh Site** (the ESRF, Grenoble), the biggest re-test of the Site and Federation kernel a single deployment can be, and the **first BLISS / Beacon / Tango / IcePAP** control plane CORA models (the rest are EPICS, or Tango / Sardana at MAX IV). Its science is soft X-ray resonant inelastic scattering (RIXS) with a ~5 m dispersive spectrometer arm, and X-ray magnetic dichroism (XMCD) plus X-ray emission spectroscopy (XES) at a 9 Tesla high-field-magnet endstation, all fed by twin APPLE-II undulators through a soft X-ray plane-grating monochromator.

ID32 coins no new Family. The twin APPLE-II undulators bind the catalog `InsertionDevice`, and the polarization is a `PseudoAxis` over the undulator phase, exactly as i06 and i10 modelled their APPLE-II sources; the PGM binds `GratingMonochromator`; the 4-circle diffractometer binds `Goniometer` with a reciprocal-space `PseudoAxis` (the Assembly named, not built, DIFF-1 / DIFF-2); the Andor CCDs bind `Camera`; the LakeShore VTI and coil-diagnostic controllers bind `TemperatureController`; the XMCD sample stage binds `LinearStage`; the machine state binds the loose `StorageRing`.

## Loose families brought to a rule-of-three (all since graduated)

ID32 pushed three loose families to a genuine rule-of-three. Per the owner decision (2026-06-27) each graduation is a dedicated, gated catalog PR rather than bundled into this scaffold; all three have since **graduated**.

| Loose family | Sightings with ID32 | ID32 binding | Status |
| --- | --- | --- | --- |
| `SpectrometerArm` | SIX + ID32 RIXS arm + ID32 XES arm + ID28 | the two dispersive spectrometer arms (the same `SpectrometerArmsController` class instantiated twice) | **graduated**: earned across SIX + ID32 RIXS/XES + ID28; presents the `Positioner` Role |
| `Magnet` | 4-ID + i10-1 + ID32 | the 9 T / 4 T XMCD split-coil magnet | **graduated**: earned across 4-ID + i10-1 + ID32; presents the `Regulator` Role, the field a settable process variable (`MAG-1` now covers only the per-Asset field detail) |
| `PolarizationAnalyzer` | 4-ID + i10 + ID32 + P09 | the RIXS scattered-beam polarimeter | **graduated** (`POL-2`): catalog Family across 4-ID / i10 / ID32 / P09, presents Positioner |

Keeping each graduation as its own PR keeps the scaffold clean and lets each get its own naming-r3 and gate-review. `SpectrometerArm` was the clearest: it presents the `Positioner` Role (an arm that positions a grating and carries a `Camera` at its focus), which is exactly why it never fit the point-Sensor families (`FluxMonitor` / `EnergyDispersiveSpectrometer`) and was coined loose at SIX.

## The BLISS / Tango control plane

ID32 is the first non-EPICS, non-Sardana controls house-style in the fleet: BLISS / Beacon (a YAML device database) over Tango and IcePAP. CORA models the control handles as opaque edge strings regardless of transport, the way the MX3 heterogeneous-control precedent does: a Tango device URL (`id32/limaccds/andor_1`), an IcePAP host+address (`iceid324`), or a BLISS axis name is the handle, carried confirm (`CTRL-1`). The RIXS / XMCD / XES acquisition runs through BLISS sequences; that orchestration is the seam CORA's edge replaces, conducting over Tango / IcePAP rather than replacing BLISS.

## Deliberately not here yet

- **The graduations (`RIXS-1`, `MAG-1`, `POL-2`).** All three families ID32 brought to a rule-of-three, `SpectrometerArm`, `Magnet`, and `PolarizationAnalyzer`, have since graduated into the catalog via their dedicated gated PRs.
- **The exact optics handles (`MONO-1`, `OPT-1`, `OPT-2`, `DIFF-1`, `SAMPLE-1`).** The PGM, mirrors, slits, diffractometer axes, and XMCD sample stage are carried confirm-pending; the decision-critical devices (the arms, the magnet, the LakeShores, the CCDs, the undulator) carry their real BLISS addresses.
- **The Assembly(Diffractometer) and the reciprocal-space rule (`DIFF-1`, `DIFF-2`).** Named, not built, as the other diffractometer beamlines deferred theirs.
- **The RIXS / XMCD / XES Methods.** Whether they enter CORA's catalog is an owner decision; the Practices render unlinked, pending, reusing the SIX RIXS, the 4-ID / i06 / i10 XMCD, and the xas_spectroscopy XES slugs (`TECH-1`).
- **The simulated devices and full asset-tree scenarios.** No `test_id32_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
