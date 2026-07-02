# Model

*The developer's by-kind index: where each CORA aggregate's ESM content lives, the `Manipulator` graduation and `ElectronAnalyzer` this deployment introduces, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at ESM |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What this deployment graduates

ESM both earns a new abstraction and consolidates two existing ones.

- **`ElectronAnalyzer` (new, since graduated).** The Scienta SES hemispherical electron energy analyzer is the ARPES detector: photon-in, electron-out, recording electron counts over a kinetic-energy by emission-angle window set by the pass energy and lens mode. No photon-detector Family covers an electron spectrometer, so ESM introduced a new `ElectronAnalyzer` Family (presents the Detector Role); it graduated into the catalog once SST (NSLS-II 7-ID HAXPES) earned the second Scienta SES (`ARPES-1`).
- **`Manipulator` (graduates).** ESM's LT six-axis UHV cryostat manipulator is the **second** UHV sample manipulator after SIX, earning the abstraction at the two-deployment threshold. `Manipulator` graduates into the catalog with this deployment, distinct from `Hexapod` (parallel-kinematic), `Goniometer` (crystal orientation), and a plain `LinearStage` / `RotaryStage`; axis count and cryo range are a per-Asset settings difference. SIX's references are swept loose to graduated in the same change. Its naming-r3 review (done at the SIX sighting, with the watch-item to confirm it is not a `Hexapod` / `Goniometer` synonym) is resolved: a serial UHV stack is a distinct mechanism.
- **`GratingMonochromator` (reuses).** ESM's PGM is the third soft X-ray plane-grating monochromator after SIX and CSX, so it binds the catalog Family rather than minting one.

## Deliberately not here yet

- **The XPEEM/LEEM branch (`21-ID-2`).** ESM's second endstation is a low-energy electron microscope (LEEM) / photoemission electron microscope (PEEM), an electron-optics imaging instrument distinct from the analyzer. It is deferred to a follow-on as a future loose `ElectronMicroscope` Family (`PEEM-1`); this cut models the ARPES branch (the 32-ID / SRX "one endstation first" precedent).

- **The sample-prep and load-lock transfer.** The sample-prep and analysis-chamber manipulators and the load-lock sample-transfer claw are present in the config but deferred; this cut models the main LT sample manipulator (`SAMPLE-1`).

- **The ARPES Method.** Whether angle-resolved photoemission enters CORA's catalog is an owner decision; the Practice renders unlinked, pending (`TECH-1`).

- **The simulated devices and full asset-tree scenarios.** No `test_esm_*.py` registers the ESM asset tree, and no vendor Models are bound. Those land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
