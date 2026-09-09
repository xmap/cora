# Notes

## Techniques

*What CORA would run at XFM: scanning X-ray fluorescence microscopy, a [Catalog](../../catalog/methods.md) Method bound through an NSLS-II [Practice](../nsls2/index.md). XFM is the second scanning-XRF beamline (after 2-ID) and follows the same Method-deferral discipline.*

XFM's science is element mapping: raster the sample through a focused beam and read the fluorescence spectrum at each point, in a step grid or a Maia continuous fly-scan. The Method below renders unlinked and stays pending until the owner-scope decision (METHOD-1) brings it into the catalog.

| Technique | Mode | Detector | Status in CORA |
| --- | --- | --- | --- |
| Scanning XRF mapping | raster (step grid or Maia fly) | `EnergyDispersiveSpectrometer` (Xspress3 / Maia) | the 2-ID `scanning_fluorescence_microscopy` Method, pending; XFM is the 2nd consumer (METHOD-1) |
| XANES microspectroscopy | energy sweep over the `EnergyAxis` | `EnergyDispersiveSpectrometer` | the BMM energy-scan question; `energy_scan` deferred (ENERGY-1), no practice |
| XRF-tomography | raster x rotation | `EnergyDispersiveSpectrometer` | out of scope: no rotation axis in the profile (TECH-1) |

### Why the Method stays pending

XFM reuses the `scanning_fluorescence_microscopy` Method that 2-ID left pending. Unlike a loose device *Family* (which a second sighting promotes on a mechanical rule-of-three), a pending *Method* has no automatic promotion: it is coined by deliberate decision when a conduct-path needs it, the same discipline that keeps `energy_scan` deferred even across several consumers. XFM makes `scanning_fluorescence_microscopy` a two-consumer Method (2-ID + XFM), which strengthens the eventual case to coin it but does not force it in a descriptor scaffold (METHOD-1). The device Roles already exist (the SDD presents the energy-dispersive Sensor, the raster stage presents Positioner), so what is pending is the recipe, not a device shape.

The XANES microspectroscopy leg sweeps the monochromator energy across an absorption edge, which leans on the deferred `energy_scan` Capability (the BMM ENERGY-1 question); no XANES practice is recorded until that Capability lands, the SRX / BMM discipline. The XRF fitting and any tomographic reconstruction are `ComputePort` work, not beamline Methods.

## Governance

*Who may act at XFM and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#safety-and-governance); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

### Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. An XFM beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

### The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may set the energy, start a raster map, run the Maia fly-scan, change the focusing optic, override a caution, or commit an energy calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody.

### The scanning map under custody

XFM's defining operation is the raster XRF map: the UTS stage sweeps the sample through the focused spot while the detectors count per pixel. CORA's Campaign and Trust shapes are where that resolves: starting a map (step or Maia fly) is a command the trust boundary gates, and the per-map energy and flux normalization are facts under custody. If an autonomous Agent were added to drive a mapping survey (a common pattern at high-throughput microprobes), it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet.

## Model

*The developer's by-kind index: where each CORA aggregate's XFM content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at XFM |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [The beamline](index.md#enclosures) (4-BM-A optics, 4-BM-C endstation) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What this deployment graduates: nothing

XFM is a clean **pure-reuse** scanning-XRF deployment, the second after 2-ID. It coins no Family and graduates nothing: the multi-element silicon-drift fluorescence detectors (the Xspress3 and the Maia) reuse `EnergyDispersiveSpectrometer` (graduated when 2-ID and 7-BM shared it), the raster stage reuses `LinearStage`, the scaler I0 channels reuse `FluxMonitor` (graduated in #353), the bending-magnet source binds the loose `Beam` PhotonBeam supply (the 2-BM / BMM precedent), and the monochromator / focusing optic / slits bind the catalog `Monochromator` / `Mirror` / `Slit`. The scanning XRF technique reuses the `scanning_fluorescence_microscopy` Method 2-ID left pending: XFM is its second consumer, which strengthens but does not coin it.

### Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring 2-ID / SRX and the other NSLS-II beamlines. Left out on purpose:

- **No catalog change.** XFM graduates nothing and coins nothing. `scanning_fluorescence_microscopy` stays pending (2-ID + XFM = 2 consumers; Methods have no mechanical promotion, the `energy_scan` deferral discipline; METHOD-1). XANES microspectroscopy leans on the deferred `energy_scan` Capability (ENERGY-1), no practice recorded.
- **The endstation-only profile.** The public profile collection exposes only the raster stage, the Xspress3, the scaler, and the Maia (in a bypass file). The bending-magnet source, the monochromator, the focusing optic, and the shutters are not in the profile, so they are carried confirm-only with no PV (no fabricated PVs; PROFILE-1). The model is honest about being thin: it asserts the device classes a BM XRF / XANES microprobe must have, with their handles pending the team.
- **The Maia detector.** XFM's signature fast continuous-mapping array (`XFM:MAIA`) is read from the bypass profile (`rvt/bypass40-maia.py`), not the active startup; it is modelled as a second `EnergyDispersiveSpectrometer` Asset and flagged (MAIA-1).
- **XRF-tomography.** Out of scope: the profile exposes an X/Y/Z raster stage but no rotation axis, so the raster-x-rotation XRF-tomography (the SRX shape) is not modelled (TECH-1).
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms.

## Open questions

*What CORA needs the XFM team to confirm. This model is reverse-engineered from public open source (the `NSLS2/xfm-profile-collection` bluesky / ophyd startup files), which is endstation-only: the raster stage and detectors are read from the `startup/*.py` device classes, but the bending-magnet source, the optics, and the shutters are not in the profile and are carried confirm-only. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

### Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The 4-BM bending-magnet source parameters (critical energy, fan, the front-end acceptance). 4-BM is a bending magnet, not an insertion device. | A bending-magnet source, recorded as a PhotonBeam Supply (the 2-BM / BMM precedent). | The source modelling. |
| PROFILE-1 | Blocks-build | The public profile collection exposes only the endstation (the raster stage + detectors). What are the source, monochromator, focusing-optic, and shutter device handles? They are carried confirm-only with no PV here. | The optics exist physically (a BM XRF / XANES microprobe needs a DCM + focusing optic + shutters); their PVs await the team. | The optics device handles. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs and the front-end / photon shutter PVs (not in the profile collection). | The permit and shutter signals are confirm notes, not guessed PVs. | The Enclosure permit + shutter signals. |
| ENC-1 | Nice-to-have | The hutch names / numbering and the A / B / C layout. The endstation PV zone is `XF:04BMC`; the optics zone is inferred. | An optics hutch (4-BM-A) plus the endstation (4-BM-C). | The Enclosure set. |

### Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The monochromator crystal cut (Si(111) is the known 4-BM crystal), d-spacing, and energy range. Not in the profile collection. | One `Monochromator` Asset, crystal settings blank. | The Monochromator settings. |
| OPT-1 | Nice-to-have | The microfocusing optic type (a KB mirror pair or a capillary) and its parameters. Not in the profile collection. | One `Mirror` Asset (the focusing optic), type to confirm. | The focusing-optic modelling. |
| ENERGY-1 | Nice-to-have | Is energy scanned as the measurement (XANES microspectroscopy sweeps the DCM across an edge), warranting the energy-scan Capability the catalog anticipates? | XANES mapped to the deferred energy_scan Capability (the BMM question). | The spectroscopy Capability decision. |

### Sample and detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The Xspress3 element count and ROI map (the profile configures four channels). | A four-channel `EnergyDispersiveSpectrometer` Asset; ROIs to confirm. | The fluorescence-detector modelling. |
| MAIA-1 | Nice-to-have | The Maia continuous-mapping detector: its element count, live status, and whether it is the primary mapping detector. It is in a bypass profile file (`rvt/bypass40-maia.py`), not the active startup. | A second `EnergyDispersiveSpectrometer` Asset (the Maia array) for fast continuous mapping. | The Maia detector modelling. |
| DIAG-1 | Nice-to-have | The SIS3820 scaler flux-channel map (which channels are I0, transmitted, the Maia deadtime). | Read-only flux (`FluxMonitor`) channels; the map blank. | The FluxMonitor bindings. |

### Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The raster-stage and optics motion-controller box models, firmware, IPs. | Family bound (MotionController), specifics blank. | The MotionController Models. |
| METHOD-1 | Blocks-go-live | Does the scanning XRF microprobe technique (`scanning_fluorescence_microscopy`) enter CORA's catalog as a Method, or stay pending? XFM is the second consumer after 2-ID. | The Method reused pending (no mechanical promotion for Methods; the energy_scan deferral discipline). | The scanning-XRF Method scope. |
| TECH-1 | Nice-to-have | Beyond XRF mapping, does XFM run XANES microspectroscopy and XRF-tomography in CORA scope? XANES leans on the deferred energy_scan; XRF-tomography would need a rotation axis (not in the profile). | XRF mapping modelled; XANES deferred (energy_scan); XRF-tomography out of scope. | The technique scope. |
