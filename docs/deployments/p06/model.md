# Model

*The developer's by-kind index: where each CORA aggregate's P06 content lives, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P06 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (KB lens fine axes) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What makes P06 new

P06 is a third beamline at an existing Site, and the fleet's fullest scanning-probe instrument. It is a hard X-ray micro- and nano-probe: a focused beam rastered across a sample while a high-rate Maia XRF array and area detectors read each point, plus nano-tomography on the NC1 sample rotation. Its novelty is the density and diversity of the device tree (six motion-controller families, two endstations, the Maia array), not any new Family or Method.

## No new families (the fullest catalog reuse yet)

P06 coins no new Family. The Maia XRF array binds `EnergyDispersiveSpectrometer` (one Asset carrying its six sub-device handles); the hexapods (MC01 plus the two NC1 KB-lens carriers) bind `Hexapod`; the KB lens fine stages bind `PseudoAxis`; the scan, sample, pin, and nano stages bind `LinearStage`; the sample rotation binds `RotaryStage`; the monochromators bind `Monochromator`; the slits bind `Slit`; the undulator binds `InsertionDevice`; the BPMs bind `FluxMonitor`; and the area / view cameras bind `Camera`. Nothing in the catalog changes.

## The control plane

P06 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as P01 / P04, but with the most controller diversity yet: OMS steppers, Aerotech fly-scan controllers, SmarAct piezo / hexapod controllers, a hexapod controller, PI and SMC-Hydra fine-stage controllers, and a Pegasus rotation controller, reading the Maia array and the Eiger / Lambda / Pilatus / PCO detectors. The handles are read from P06's public OnlineXML registry and carried confirm (`CTRL-1`); several detectors report on a bare `p06` / `petra3` host (`HOST-1`). The scanning fluorescence acquisition is a continuous-motion Aerotech fly-scan coupled to the Maia readout; CORA's edge conducts that over its `ControlPort` and is barred from the deterministic real-time fly-scan loop by construction.

## Deliberately not here yet

- **The undulator parameters (`SRC-1`).** The OnlineXML exposes the gap / harmonic / taper, not the period; carried pending.
- **The optics physical detail (`OPT-1`).** The DCM crystal cut, the multilayer d-spacing, and the KB focal sizes are carried confirm-pending.
- **The motor-bank axis roles (`GROUP-1`).** The `mono_mot`, `mi_mot`, and `nat_mot` banks carry no per-axis role in the registry; grouped as stage Assets, roles pending.
- **The fly-scan parameters (`SCAN-1`).** The Aerotech raster trajectories and the motion-detector triggering coupling are not in the registry.
- **The detector roster (`DET-1`).** The operative detectors per experiment, the Maia element count, and the area-detector models are named, not fully bound; the Maia sub-device split is a modelling question.
- **The host mapping (`HOST-1`).** Several detectors report on a bare host; whether that is a shared Tango DB or a registry artifact is pending.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The scanning / nano-tomography Methods (`TECH-1`).** Whether these enter CORA's catalog is an owner decision; the Practices render unlinked, pending, reusing the existing slugs.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p06_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
