# Notes

## Techniques

*What the modelled part of P01 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P01 runs hard X-ray dynamics techniques (nuclear resonant scattering and resonant inelastic scattering) that earn no catalog Method today, so the Methods below render unlinked and are carried pending until a technique enters scope (`TECH-1`).

### Nuclear resonant scattering (EH1)

P01 sets the X-ray energy onto a Moessbauer isotope's nuclear resonance with the [double-crystal monochromator](source.md), then carves a meV / Moessbauer-energy bandwidth with the [high-resolution monochromator stack](sample.md) (the four nested / channel-cut HRMs). Scanning the high-resolution-monochromator energy axis while reading the time- and energy-resolved detector signal produces the nuclear inelastic / resonant spectrum.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Nuclear resonant scattering / nuclear inelastic scattering | `inelastic_x_ray_scattering` | the high-resolution-monochromator energy scan reading the avalanche-photodiode signal; no catalog Method fits, reuses the IXS slug ESRF ID28 / NSLS-II IXS share, a further consumer (`TECH-1`) |

### Resonant inelastic X-ray scattering (EH3)

P01's EH3 endstation focuses the beam with the [KB mirror pair](sample.md) onto the sample and analyzes the inelastically scattered photons on the spectrometer arm, scanning the incident energy against the analyzed energy to map the excitation spectrum.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Resonant inelastic X-ray scattering | `resonant_inelastic_scattering` | KB-focused incident beam analyzed on the EH3 spectrometer; reuses the RIXS slug SIX / ESRF ID32 share, a further consumer (`TECH-1`) |

### Diffraction (EH2)

P01's EH2 endstation carries a theta / two-theta [goniometer](sample.md) reading a detector on a positioning stage, for hard X-ray diffraction. The catalog carries no general diffraction Method today; the technique is noted, not bound, pending confirmation of the endstation's routine use (`TECH-1`, `DIFF-1`).

### A new technique branch on familiar vocabulary

P01 is the fleet's NRS / RIXS dynamics beamline. Its techniques are new to CORA's catalog (which is tomography- and MX-centric today), but they reuse the inelastic- and resonant-inelastic-scattering slugs already carried pending across the fleet (ESRF ID28 IXS, ESRF ID32 / SIX RIXS, NSLS-II IXS), so none forces a new Method to be coined now. The instrument anatomy reuses existing Families end to end: the monochromators bind `Monochromator`, the KB mirrors `Mirror`, the lens `Transfocator`, the stages `LinearStage` / `RotaryStage` / `Table`, the sample circle `Goniometer`.

### Not modelled yet

The concrete acquisition recipes (the high-resolution-monochromator energy-scan sequences and their exposures, the RIXS incident-energy scans, the diffraction scans) are not written yet; they join as the deployment approaches the point where CORA drives P01. Whether the NRS / RIXS Methods enter CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at P01, and the trust shape that will gate it. First cut.*

Governance at P01 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P01 is CORA's first PETRA III beamline, so the DESY operator pool and the safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance), shared across the facility's beamlines, until DESY staff confirm them (`GOV-1`). P01 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P01, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals (across the two optics and three experiment hutches) and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

P01 also carries the hazard classes that come with its endstations: the high-resolution-monochromator stack and the KB optics are precision instruments inside interlocked hutches, and the five-hutch layout means several enclosures gate the beam in series. Those land with the instruments that bring them when the deployment firms up.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P01, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's P01 content lives, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P01 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (coupled mono energy) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes P01 new

P01 is a new Site's first beamline, and two things genuinely new at the modelling level. It is **CORA's first PETRA III beamline** and a further **Tango / Sardana control floor** (after MAX IV and ALBA). Its science is hard X-ray dynamics: nuclear resonant scattering in EH1, diffraction in EH2, and RIXS in EH3, across 2.5-80 keV.

- **The control plane (`CTRL-1`).** PETRA III runs Tango with Sardana as the scan layer. P01 is the first deployment whose device handles were read from a DESY OnlineXML registry, the Tango analog of the ESRF BLISS Beacon config and the APS Guarneri `devices.yml`. The OnlineXML extractor that produced the candidate is `reverse_engineer/` in the (private) `xmap/research` repo (the `--source onlinexml` path).
- **The technique branch (`TECH-1`).** NRS and RIXS are new to CORA's catalog but reuse the IXS / RIXS slugs already carried pending across the fleet, so no Method is coined now.

### No new families (the optics / motion spine reuses the fleet precedent)

P01 coins no new Family. The monochromators bind `Monochromator` and the coupled energy is a `PseudoAxis`; the mirrors (deflection and KB) bind `Mirror`; the slits bind `Slit`; the CRL binds `Transfocator`; the undulator binds `InsertionDevice`; the stages bind `LinearStage` / `RotaryStage` / `Table`; the EH2 sample circle binds `Goniometer`; the BPM / ion chamber / diamond monitor bind `FluxMonitor`. Nothing in the catalog changes.

The one binding worth calling out: the EH2 sample circle is modelled as a **`Goniometer`** Asset (the catalog Family), not the composed **`Diffractometer`** Assembly. The OnlineXML exposes only theta / two-theta; the `Diffractometer` Assembly requires a goniometer plus a detector arm plus a reciprocal-space layer, none of which the registry confirms. This follows the catalog's own guidance (the TARDIS E6C precedent) and is carried `DIFF-1`.

### The control plane

P01 sits on the PETRA III Tango device floor with Sardana as the scan / motion SCADA layer (Pool / MacroServer / MeasurementGroup, Spock CLI, Taurus UIs). A motion axis is a Tango motor device (`p01/motor/<hutch>.<n>`), a coupled axis is a virtual-motor executor (`p01/vmexecutor/<name>`), and a scan is a Sardana macro. The handles are read from P01's public OnlineXML registry and carried confirm; the device servers live in `tango-ds/deviceclasses`, the Sardana fork in `fsec-sardana` (`CTRL-1`). The NRS / RIXS acquisition runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`, conducting over the Tango floor rather than owning it. The NeXus file-writing (the `nexdatas` chain) is plumbing CORA observes, not data it owns.

### Deliberately not here yet

- **The detector devices (`DET-1`).** The OnlineXML carries detector positioning stages, not the detector device servers; the APD / RIXS / diffraction detectors are named, not bound.
- **The physical optics detail (`MONO-1`, `NRS-1`, `OPT-1`).** The DCM crystal cut, which HRM is in beam per isotope, the mirror coatings, the KB bend radii, and the CRL recipe are carried confirm-pending.
- **The goniometer geometry (`DIFF-1`).** The EH2 circle count beyond theta / two-theta, and whether it composes a Diffractometer Assembly, is pending.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The NRS / RIXS Methods (`TECH-1`).** Whether these enter CORA's catalog is an owner decision; the Practices render unlinked, pending, reusing the IXS / RIXS slugs.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p01_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the P01 team to confirm before the model can be trusted.*

P01 was reverse-engineered from P01's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p01](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p01), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry carries real Tango device names and control handles, but no physical detail (crystal cuts, energy ranges, bend radii, detector models). P01 is CORA's first PETRA III beamline and a further Tango / Sardana control floor (after MAX IV and ALBA). Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: two optics hutches (OH1, OH2) feeding three experiment hutches (EH1, EH2, EH3), or a different layout? | Two `p01-oh*` optics hutches and three `p01-eh*` experiment hutches, read from the OnlineXML host names. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The undulator period and parameters, and whether gap_a/gap_b/taper_a/taper_b mean two sections or a canted arrangement. | An undulator source, 2.5-80 keV; gap / taper virtual axes only. | The source Asset detail. |
| GROUP-1 | Nice-to-have | The Asset grouping of the registry's per-axis device list into instruments (one monochromator, one mirror, one sample stage). | The groupings on the [device pages](index.md), inferred from the axis name prefixes. | The Asset boundaries. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MONO-1 | Blocks-go-live | The double-crystal monochromator crystal cut (Si 111 / 311) and energy range. | A DCM bound to `Monochromator`; Bragg / energy virtual axes read from the registry. | The monochromator modelling. |
| OPT-1 | Nice-to-have | The deflection-mirror coatings / stripes and incidence angles, the KB bend radii and focal sizes, the CRL lens count / material, and the diamond-monitor / RIXS-pre-optic roles. | Two OH1 mirrors and the EH3 KB pair bound to `Mirror`; the CRL bound to `Transfocator`; the diamond monitor bound to `FluxMonitor`; handles read, physical detail pending. | The optics Asset detail. |

### Sample endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| NRS-1 | Blocks-go-live | The four EH1 high-resolution monochromators (400 / 1064 / 3D / 3W): which is in beam per Moessbauer isotope and resolution, and how the `hrm_ener` virtual axis couples them. | Four `Monochromator` Assets plus a `HighResMonoEnergy` `PseudoAxis`; selection per isotope pending. | The NRS instrument modelling. |
| DIFF-1 | Blocks-go-live | The EH2 diffractometer geometry: the full circle count beyond theta / two-theta, and whether it composes a Diffractometer Assembly with a detector arm. | A `Goniometer` Asset (theta / two-theta), not the composed Diffractometer Assembly, until a detector arm is confirmed. | The diffractometer modelling. |
| SAMPLE-1 | Nice-to-have | The EH3 RIXS sample-stage axes and sample-environment detail. | A `LinearStage` (x / y / b / rot / tilt) read from the registry. | The sample-stage modelling. |

### The detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector models per endstation (the EH1 NRS avalanche photodiode, the EH2 diffraction detector, the EH3 RIXS spectrometer detector), which the OnlineXML does not carry as motor rows. | Detector positioning stages bound to `LinearStage`; the detector devices named, not bound. | The detector modelling. |
| DIAG-1 | Nice-to-have | The beam-position-monitor, ion-chamber, and diamond-monitor handles and roles. | `FluxMonitor` positioning stages read from the registry. | The diagnostics modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P01 device, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Do nuclear resonant scattering and RIXS enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the `inelastic_x_ray_scattering` and `resonant_inelastic_scattering` slugs; none coined. | The technique Capabilities. |
