# Model

*The developer's by-kind index: where each CORA aggregate's P01 content lives, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P01 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (coupled mono energy) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What makes P01 new

P01 is a new Site's first beamline, and two things genuinely new at the modelling level. It is **CORA's first PETRA III beamline** and a further **Tango / Sardana control floor** (after MAX IV and ALBA). Its science is hard X-ray dynamics: nuclear resonant scattering in EH1, diffraction in EH2, and RIXS in EH3, across 2.5-80 keV.

- **The control plane (`CTRL-1`).** PETRA III runs Tango with Sardana as the scan layer. P01 is the first deployment whose device handles were read from a DESY OnlineXML registry, the Tango analog of the ESRF BLISS Beacon config and the APS Guarneri `devices.yml`. The OnlineXML extractor that produced the candidate is `scripts/reverse_engineer/` (the `--source onlinexml` path).
- **The technique branch (`TECH-1`).** NRS and RIXS are new to CORA's catalog but reuse the IXS / RIXS slugs already carried pending across the fleet, so no Method is coined now.

## No new families (the optics / motion spine reuses the fleet precedent)

P01 coins no new Family. The monochromators bind `Monochromator` and the coupled energy is a `PseudoAxis`; the mirrors (deflection and KB) bind `Mirror`; the slits bind `Slit`; the CRL binds `Transfocator`; the undulator binds `InsertionDevice`; the stages bind `LinearStage` / `RotaryStage` / `Table`; the EH2 sample circle binds `Goniometer`; the BPM / ion chamber / diamond monitor bind `FluxMonitor`. Nothing in the catalog changes.

The one binding worth calling out: the EH2 sample circle is modelled as a **`Goniometer`** Asset (the catalog Family), not the composed **`Diffractometer`** Assembly. The OnlineXML exposes only theta / two-theta; the `Diffractometer` Assembly requires a goniometer plus a detector arm plus a reciprocal-space layer, none of which the registry confirms. This follows the catalog's own guidance (the TARDIS E6C precedent) and is carried `DIFF-1`.

## The control plane

P01 sits on the PETRA III Tango device floor with Sardana as the scan / motion SCADA layer (Pool / MacroServer / MeasurementGroup, Spock CLI, Taurus UIs). A motion axis is a Tango motor device (`p01/motor/<hutch>.<n>`), a coupled axis is a virtual-motor executor (`p01/vmexecutor/<name>`), and a scan is a Sardana macro. The handles are read from P01's public OnlineXML registry and carried confirm; the device servers live in `tango-ds/deviceclasses`, the Sardana fork in `fsec-sardana` (`CTRL-1`). The NRS / RIXS acquisition runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`, conducting over the Tango floor rather than owning it. The NeXus file-writing (the `nexdatas` chain) is plumbing CORA observes, not data it owns.

## Deliberately not here yet

- **The detector devices (`DET-1`).** The OnlineXML carries detector positioning stages, not the detector device servers; the APD / RIXS / diffraction detectors are named, not bound.
- **The physical optics detail (`MONO-1`, `NRS-1`, `OPT-1`).** The DCM crystal cut, which HRM is in beam per isotope, the mirror coatings, the KB bend radii, and the CRL recipe are carried confirm-pending.
- **The goniometer geometry (`DIFF-1`).** The EH2 circle count beyond theta / two-theta, and whether it composes a Diffractometer Assembly, is pending.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The NRS / RIXS Methods (`TECH-1`).** Whether these enter CORA's catalog is an owner decision; the Practices render unlinked, pending, reusing the IXS / RIXS slugs.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p01_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
