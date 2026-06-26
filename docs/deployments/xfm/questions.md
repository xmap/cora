# Open questions

*What CORA needs the XFM team to confirm. This model is reverse-engineered from public open source (the `NSLS2/xfm-profile-collection` bluesky / ophyd startup files), which is endstation-only: the raster stage and detectors are read from the `startup/*.py` device classes, but the bending-magnet source, the optics, and the shutters are not in the profile and are carried confirm-only. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

## Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The 4-BM bending-magnet source parameters (critical energy, fan, the front-end acceptance). 4-BM is a bending magnet, not an insertion device. | A bending-magnet source, recorded as a PhotonBeam Supply (the 2-BM / BMM precedent). | The source modelling. |
| PROFILE-1 | Blocks-build | The public profile collection exposes only the endstation (the raster stage + detectors). What are the source, monochromator, focusing-optic, and shutter device handles? They are carried confirm-only with no PV here. | The optics exist physically (a BM XRF / XANES microprobe needs a DCM + focusing optic + shutters); their PVs await the team. | The optics device handles. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs and the front-end / photon shutter PVs (not in the profile collection). | The permit and shutter signals are confirm notes, not guessed PVs. | The Enclosure permit + shutter signals. |
| ENC-1 | Nice-to-have | The hutch names / numbering and the A / B / C layout. The endstation PV zone is `XF:04BMC`; the optics zone is inferred. | An optics hutch (4-BM-A) plus the endstation (4-BM-C). | The Enclosure set. |

## Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The monochromator crystal cut (Si(111) is the known 4-BM crystal), d-spacing, and energy range. Not in the profile collection. | One `Monochromator` Asset, crystal settings blank. | The Monochromator settings. |
| OPT-1 | Nice-to-have | The microfocusing optic type (a KB mirror pair or a capillary) and its parameters. Not in the profile collection. | One `Mirror` Asset (the focusing optic), type to confirm. | The focusing-optic modelling. |
| ENERGY-1 | Nice-to-have | Is energy scanned as the measurement (XANES microspectroscopy sweeps the DCM across an edge), warranting the energy-scan Capability the catalog anticipates? | XANES mapped to the deferred energy_scan Capability (the BMM question). | The spectroscopy Capability decision. |

## Sample and detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The Xspress3 element count and ROI map (the profile configures four channels). | A four-channel `EnergyDispersiveSpectrometer` Asset; ROIs to confirm. | The fluorescence-detector modelling. |
| MAIA-1 | Nice-to-have | The Maia continuous-mapping detector: its element count, live status, and whether it is the primary mapping detector. It is in a bypass profile file (`rvt/bypass40-maia.py`), not the active startup. | A second `EnergyDispersiveSpectrometer` Asset (the Maia array) for fast continuous mapping. | The Maia detector modelling. |
| DIAG-1 | Nice-to-have | The SIS3820 scaler flux-channel map (which channels are I0, transmitted, the Maia deadtime). | Read-only flux (`FluxMonitor`) channels; the map blank. | The FluxMonitor bindings. |

## Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The raster-stage and optics motion-controller box models, firmware, IPs. | Family bound (MotionController), specifics blank. | The MotionController Models. |
| METHOD-1 | Blocks-go-live | Does the scanning XRF microprobe technique (`scanning_fluorescence_microscopy`) enter CORA's catalog as a Method, or stay pending? XFM is the second consumer after 2-ID. | The Method reused pending (no mechanical promotion for Methods; the energy_scan deferral discipline). | The scanning-XRF Method scope. |
| TECH-1 | Nice-to-have | Beyond XRF mapping, does XFM run XANES microspectroscopy and XRF-tomography in CORA scope? XANES leans on the deferred energy_scan; XRF-tomography would need a rotation axis (not in the profile). | XRF mapping modelled; XANES deferred (energy_scan); XRF-tomography out of scope. | The technique scope. |
