# Open questions

*What CORA needs the i06 team to confirm before the model can be trusted.*

i06 was reverse-engineered from the beamline's own bluesky device layer ([DiamondLightSource/dodal](https://github.com/DiamondLightSource/dodal): the `src/dodal/beamlines/i06*.py` factories and the `src/dodal/devices/` classes), so the control handles in the [Inventory](inventory.md) are the beamline's real PVs, read from dodal rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | Are the PV zones BL06I (optics spine), BL06J (i06-1), and BL06K (i06-2) three separate hutches, and how do the two endstations share the source? | Three enclosures: a shared `i06-optics` zone and the `i06-1` and `i06-2` experiment hutches. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The two APPLE-II undulator periods, the gap range, and how the downstream (IDD) and upstream (IDU) devices coordinate to feed the branches. | Two `InsertionDevice` Assets; period and coordination carried pending. | The source Asset detail. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The storage-ring state i06 reads (current, fill, machine mode). | Observe-only machine state on `SR-DI-DCCT-01` / `CS-CS-MSTAT-01` / `SR-CS-FILL-01`, a loose `StorageRing`. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The plane-grating monochromator gratings (line densities), the cff fixed-focus constant, and the incident-energy range and partition rule. | A soft X-ray PGM bound to `GratingMonochromator`, 70-2200 eV, gratings 150 / 400 / 1200 l/mm; the energy pseudo-axis decomposes to the PGM and the APPLE-II gap. | The monochromator and incident-energy Assets. |
| POL-2 | Blocks-go-live | The IDD / IDU asymmetry: only the upstream IDU exposes the driven energy / polarization handles in dodal, while the downstream IDD stops at its controller. Should CORA expose a symmetric IDD handle? | The energy and polarization pseudo-axes are over the upstream IDU; the IDD is a sibling `InsertionDevice` Asset. | The source-axis wiring. |

## Beam axes: polarization

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| POL-1 | Blocks-go-live | The polarization value domain (LH / LV / PC / NC / LA plus third-harmonic variants) and the polarization-to-phase conversion: should CORA pin the conversion as a LookupTable Calibration, or run the polarization pseudo-axis rule-less and let the live i06 controller own the kinematics? | A `PseudoAxis` over the APPLE-II phase rows, value domain as listed, carried rule-less by default (the controller owns the conversion). | The polarization-axis modelling. |

## Diffraction-dichroism endstation (i06-1)

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-go-live | The i06-1 diffraction-dichroism circle roles (sample theta incidence, chi / phi orientation, the DET:2THETA / DET:Y detector arm) and whether they compose an Assembly. | A `Goniometer` for the sample circles plus a detector arm; the `Assembly(Diffractometer)` is named, not built. | The diffractometer geometry; the CORA structural modelling is on [Model](model.md#deliberately-not-here-yet). |
| DIFF-2 | Nice-to-have | The reciprocal-space coordination over the diffraction-dichroism circles (the inverse-kinematics rule). | A reciprocal-space `PseudoAxis` over the circles, the rule deferred as on 4-ID / 8-ID / CSX. | The reciprocal-space Asset. |
| STAGE-1 | Nice-to-have | Whether the absorption-stage theta (and the diffractometer chi / phi) warrant a `Goniometer` plus Assembly rather than the `LinearStage` placeholder. | The absorption stage bound to `LinearStage` as a design-phase placeholder. | The absorption-stage Family. |
| TEMP-1 | Nice-to-have | The Lakeshore 336 cooling and heating ranges and channel assignment. | Two `TemperatureController` Assets presenting the `Regulator` Role; cooling-vs-heating a per-Asset setting; ranges pending. | The temperature-control modelling. |
| DET-1 | Blocks-go-live | The i06-1 diffraction scattering detector and any incident-flux / drain-current (electron-yield) monitor: both are absent from dodal. | Not modelled as devices: the geometry is modelled now and the detector(s) bound later from outside dodal; no detector Family invented. | The detector modelling. |

## PEEM endstation (i06-2)

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MANIP-1 | Blocks-go-live | The PEEM sample-manipulator axis sets (the i06-2 `peem` x / y / phi plus the es energy-slit translation, and the i06-branch sample stage). | Two `Manipulator` Assets reusing the graduated Family; axis sets carried pending. | The manipulator modelling. |
| PEEM-1 | Blocks-go-live | The PEEM electron-optical column and its magnified electron-image detector: both are absent from dodal. | Not modelled: the electron-imaging column is the `ElectronMicroscope` anatomy, deferred until its PVs are sourced; not coined here. | The PEEM imaging-detector modelling; the CORA family decision is on [Model](model.md#deliberately-not-here-yet). |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from dodal current and correct? | The handles in the descriptor are taken from dodal and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals and the photon / front-end shutters (absent from dodal). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent (the soft X-ray optics and the UHV endstations) and the cooling supply. | Photon beam, cooling water, and ultra-high vacuum on the optics and endstations. | The Supply observations. |
| GOV-1 | Nice-to-have | The Diamond operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the Diamond Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Do the soft X-ray dichroism and resonant-scattering techniques (XMCD, XMLD, resonant diffraction) enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices; XMCD and resonant scattering share the 4-ID Methods, XMLD is a new pending slug; none coined. | The dichroism / resonant Capabilities. |
