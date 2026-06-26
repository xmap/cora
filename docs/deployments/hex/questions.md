# Open questions

*What CORA needs the HEX team to confirm before the model can be trusted.*

HEX was reverse-engineered from public sources (the BNL beamline page, the [beamline 27-ID wiki](https://wiki-nsls2.bnl.gov/beamline27ID), and the beamline's bluesky profile collection [NSLS2/hex-profile-collection](https://github.com/NSLS2/hex-profile-collection) and [NSLS2/hextools](https://github.com/NSLS2/hextools)), so the control handles in the [Inventory](inventory.md) are read from public config rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | Are the six designed enclosures A (FOE), B, C, D, E, F, with only A and F presently relevant to operations (B not erected; C / D / E future-upgrade shells)? | All six declared; `hex-foe` and `hex-endstation` carry devices, B to E are device-free forward-looking shells. | The Enclosure grouping and the future-hutch contents. |
| SAT-1 | Nice-to-have | Is the satellite building housing the F-hutch the same as Bldg. 742 or a separate numbered structure adjacent to it? | The F-hutch is a distinct enclosure adjacent to Bldg. 742, bound to the NSLS-II Site. | The endstation Enclosure detail. |
| LAYOUT-1 | Nice-to-have | The source-to-F-hutch distance (about 100 m) and whether an exact per-hutch z-position table exists. | About 100 m source to endstation; no per-hutch z table carried. | The beam-path geometry. |
| BRANCH-1 | Nice-to-have | Do the inboard and outboard front-end branches carry any installed optics, or are they bare provisions for the future hutches? | Provisions only; only the center branch carries devices. | The front-end slit modelling. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The storage-ring state HEX reads (current, fill, status). | Observe-only machine state, a loose `StorageRing`; the exact PVs pending. | The machine-state observation. |
| SCW-1 | Nice-to-have | The superconducting wiggler pole count and critical photon energy (only the 4.3 T field, 70 mm period, 1.2 m length, cell-27 straight are published). | An `InsertionDevice` Asset; field, period, and length carried as specs; pole count and critical energy pending. | The source Asset detail. |
| MONO-1 | Blocks-go-live | The monochromator crystal material and geometry (is it Si(111) bent Laue?), the crystal count, and the d-spacing. | A single bent-Laue first crystal on a vertical translation, binding `Monochromator`; the incident energy a `PseudoAxis` over it. | The monochromator and incident-energy Assets. |
| MONO-2 | Blocks-build | The upper monochromatic energy: 150 keV (the wiki) or 200 keV (peer-reviewed, "first NSLS-II beamline to reach 200 keV mono")? | 30 to 200 keV monochromatic, 30 to 250 keV white. | The energy-axis range bound. |
| FILT-1 | Nice-to-have | The FOE low-energy filter materials and thicknesses per branch (center SiC 3 / 6 / 9 / 12 mm; outboard / inboard Cu plus SiC) and the 35 mm pitch. | Beam-hardening filters bound to `Filter`; materials and thicknesses as listed on the commissioning wiki. | The filter Asset detail. |
| FOCUS-1 | Nice-to-have | What focusing optic is being commissioned for the monochromatic beam, and the target focused spot. | Focusing not yet a device; carried deferred. | The focusing-optic Asset. |

## Sample

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | The modular sample-tower configurations (A to D), the 500 kg capacity, and which axes are motorized (the tomographic rotation and the translations). | One reconfigurable tower (`Table`, 500 kg, configs A to D) plus a `RotaryStage` rotation and `LinearStage` translations; capacity and config set as settings. | The sample-stage modelling. |
| INSITU-1 | Blocks-go-live | Which in-situ rigs are actually installed or available at the endstation (load frames, furnaces, cryostats, battery cyclers)? | None installed; the endstation is "capable of housing" user-brought environments, so no in-situ rig is modelled. | The sample-environment modelling; the CORA family decision is on [Model](model.md#deliberately-not-here-yet). |

## Detection

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The PerkinElmer area-detector model (XRD1621?), its pixel count, and that it is the angle-dispersive / powder-diffraction (ADXD) detector. | A PerkinElmer XRD1621 flat panel binding `Camera`, inferred to be the ADXD detector. | The area-detector modelling. |
| DET-2 | Blocks-go-live | The GeRM germanium strip detector channel count, energy resolution, and the EDXD gauge-volume dimensions. | A GeRM strip detector binding the existing `EnergyDispersiveSpectrometer` Family; specs pending. | The energy-dispersive-detector modelling. |
| DET-3 | Nice-to-have | Which Kinetix camera is the tomography default, and the scintillator / lens magnification options behind the "2 & 4 mm", "20 & 40 mm", and "Dual cam" imaging-table positions. | `kinetix1` is the default; the scintillator-lens table binds `Scintillator`; the Phantom Veo is the high-speed camera. | The imaging-camera and scintillator modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the profile collection current and correct, and what are the FOE-optics PVs (absent from it)? | The endstation detector handles are from the profile collection and carried confirm; the FOE-optics PVs are pending. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals and the photon / front-end shutters (absent from the profile collection). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent (the FOE optics) and the cooling supply. | Photon beam, cooling water, and vacuum on the FOE optics; the cryogen-free wiggler draws no liquid helium. | The Supply observations. |
| GOV-1 | Nice-to-have | The NSLS-II operator pool and safety-review structure (site-level), and the NYSERDA-aligned beamtime-reservation fraction and the proposal-evaluation committee's scoring split. | Carried pending on the NSLS-II Site; the NYSERDA allocation Policy layered on top, fraction and scoring pending. | The governance principals and allocation Policy. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Is the operational technique set exactly imaging / tomography, radiography, EDXD, and powder / ADXD, with all three diffraction-and-imaging modes available in the one endstation, and are PDF and 3DXRD not offered? | Those techniques only; multi-technique in one endstation via detector / optics positioning; no PDF, no 3DXRD. | The technique Capabilities and the multi-technique modelling. |
