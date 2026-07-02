# Model

*The developer's by-kind index: where each CORA aggregate's Cristallina content lives, how the diffractometers reuse the graduated Assembly and the vector magnet binds an earned Family, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at Cristallina |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (the reciprocal-space `PseudoAxis`) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## The headline: no new Family, three things tested

Cristallina coins **no new Family**, the same finding as Alvra and Bernina. But it tests the model against three things the prior PSI stations did not have, and the interest is in how each is absorbed by existing shapes.

### The diffractometers reuse the graduated Assembly (DIFF-1)

Cristallina-Q has two diffraction platforms: DM1 (the dilution-fridge diffractometer, `SARES31-GPS`) and DM2 (the pulsed-magnet diffractometer, `SARES32-GPS`). Both are built by the `slic` `Diffractometer` driver from ECMC servo-motor axes (twotheta / theta plus base and sample translations; DM2 adds rot_x / rot_z swivels). As at [Bernina](../bernina/model.md), each is the graduated [`Diffractometer` Assembly](../../catalog/assemblies.md): a composed `Goniometer` (the sample circles) plus a `RotaryStage` detector-arm circle plus a reciprocal-space `PseudoAxis`. The GPS / XRD platforms at Bernina were the Assembly's third and fourth bindings; the Cristallina DM1 / DM2 are its fifth and sixth. No new Family or Assembly is coined (DIFF-1; the reciprocal-space partition rule is DIFF-2). DM2's PV channels are commented out of the active `slic` config, so it is carried as present-hardware-not-acquired (DISABLED-1).

### The vector magnet is a further `Magnet` consumer (MAG-1)

The DilSc sample environment is a dilution refrigerator with a 3-axis vector superconducting magnet (an Oxford Mercury iPS, field limits X,Y = ±0.6 T and Z = ±5.2 T). The magnet binds the **graduated `Magnet`** Family, whose rule-of-three was earned across 4-ID, i10-1, and ESRF ID32 (the 9 T XMCD magnet). Cristallina is a **further consumer**, binding the catalog Family like any other (MAG-1 now covers only the per-Asset field ranges and control handles). The `Magnet` Family presents the `Regulator` Role, the field a settable process variable, and the LakeShore 372 thermometry / heater binds the **graduated `TemperatureController`** Family (also presents the Regulator Role), the ID32 VTI precedent. The vector geometry (three independently-ramped field axes) is a richer setting than the single-axis magnets, but it is a per-Asset setting, not a Family split, the same way the diffractometer axis counts are.

### The absent pump-probe laser (LASER-1, reframed)

Alvra and Bernina each carry a pump-probe `Laser` and an arrival-time monitor. Cristallina's `slic` source has neither: no `SLAAR` / `PALM` / `PSEN` devices appear, and the only laser is the X-ray alignment laser (`SAROP31-OLAS147`, a catalog `Laser`). Pump-probe timing is mediated by the CTA sequencer (`SAR-CCTA-ESC`) and the EVR, with a server-side pulse-tube synchronization service (`oscillations.psi.ch`). So this cut models no pump-probe-laser Asset. Whether Cristallina has a pump-probe laser in a different controls layer (as Alvra and Bernina do in `eco`'s `loptics`) is carried as an open question rather than invented (LASER-1).

## The provenance boundary: slic, in-repo

Cristallina is CORA's first deployment mined from `slic` rather than `eco`. The boundary is cleaner than Bernina's: where Bernina's `eco` config loaded its device list from a non-public JSON, Cristallina's `slic` repo keeps the device identities, axes, and PV prefixes as in-repo Python literals. What is non-public is only runtime state, not device definitions: the working directory and data paths, a PSSS motion helper script, the DilSc SECoP / Frappy magnet server (`dilsc.psi.ch:5000`, an alternative to the live EPICS driver), and the pulse-tube synchronization HTTP service (server-side). Those are recorded under `software_iocs_not_modeled` and ENV-1, not modelled.

One provenance caution shapes the inventory: many `slic` drivers are instantiated but their PV channels are commented out of the active tuples (DM2, several SmarAct stages, the Attocube, the PuMa stack, the cameras). These are carried as present-hardware-not-acquired where carried at all (DISABLED-1), not as live Assets.

## The architectural gap register (shared with the other XFELs)

These are the same deferrals Alvra and Bernina recorded; Cristallina re-confirms them a third time at PSI, now in a vector-magnet diffraction context.

- **One switched Aramis source feeding co-equal stations (TOPO-1).** Now the full triad: Cristallina is the third root Unit on the same source as Alvra and Bernina. Three co-equal Units sharing one upstream source has no home except the `Supply("PhotonBeam")` seam, and the routing state has no model.
- **Per-shot, pulse-ID-tagged event DAQ (DAQ-1).** The `sf-daq` records a free-running `bsread` stream of per-shot frames; CORA's poll-to-Done acquisition has no representation for it. The Run stays the provenance envelope and the per-shot plane is a referenced `Dataset`.
- **Beam-synchronous event timing (TIMING-1).** The CTA sequencer and EVR gate acquisition at beam rate (and here also mediate the pump-probe delay, in the absence of a laser device); `TimingController` carries the device but the trigger pattern has no typed home.

## What is deliberately not here yet (modelling, as at the other exercises)

- **New Capabilities / Methods and vendor Models.** Cristallina earns no catalog change; the diffraction and serial-crystallography recipes are carried pending on the [PSI Practices](../psi/index.md). No catalog Model is bound.
- **The pump-probe laser layer (LASER-1).** Absent from `slic`; not invented.
- **The vector-magnet field ranges and control handles (MAG-1).** The `Magnet` Family has graduated (Cristallina is a further consumer); only the per-Asset field detail stays pending.
- **The disabled stages (DISABLED-1).** DM2, the SmarAct / Attocube / PuMa stages, and the cameras are instantiated but commented out of the active config; carried as present-hardware, not live Assets.
- **The serial-crystallography sample delivery (SAMPLE-1).** Beyond the fast XY stage, the Cristallina-MX delivery is deferred.
- **The transmission-readback cross-reference (XREF-1).** The front-end attenuator's transmission readbacks alias to `SAROP31-OATT053`; carried `confirm`.
- **Integration scenarios.** No `test_cristallina_*.py` registers Cristallina Assets. Hard-registering a design-phase, off-roadmap, XFEL beamline would commit speculative structure.
