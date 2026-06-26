# Open questions

*What CORA needs the ISR team to confirm before the model can be trusted.*

ISR was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/isr-profile-collection](https://github.com/NSLS2/isr-profile-collection)), which is an early / commissioning, optics-first scaffold. The control handles in the [Inventory](inventory.md) are the beamline's real PVs, read from the `startup/` files rather than confirmed by staff, and the devices ISR's mission implies are largely absent from the source. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## The mission gaps (the headline)

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-go-live | The multi-circle diffractometer: only two axes (`th`, `zeta`) are bound under the `Dif:ISD` IOC. What are the full sample-orientation circles, the detector two-theta arm, and the reciprocal-space / hkl engine that resonant and surface (CTR) diffraction need? | One `RotaryStage` for the two bound axes; the full diffractometer is absent and not modelled. | The sample-orientation and detection-geometry modelling. |
| INSITU-1 | Blocks-go-live | The in-situ sample environment: despite In Situ being the beamline's name, no temperature controller, electrochemistry / potentiostat, gas / flow, or cryostat is PV-bound. Which in-situ environments exist and what are their PVs? | No in-situ device modelled; carried as a named gap. | The in-situ sample-environment modelling. |
| RESONANT-1 | Blocks-go-live | The resonant energy axis and polarization analysis: the DCM Bragg is the physical energy axis but a wired energy pseudo-axis is only a non-functional stub, and no polarization analyzer or phase retarder is bound. How is energy scanned for resonant work, and is polarization analyzed? | Energy via the DCM Bragg; no energy pseudo-axis or polarization device modelled. | The resonant-scattering modelling. |

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | Are the optics zones (FE:C04A, XF:04IDA-OP, XF:04IDB-OP) and the zone-D endstation (XF:04IDD-ES) separate hutches? | Two enclosures: an `isr-optics` zone and the `isr-endstation` hutch. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The in-vacuum undulator model and energy range (only a read-only gap encoder is bound; no gap-drive setpoint). | An `InsertionDevice` undulator, observed gap; parameters pending. | The source Asset detail. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The storage-ring state ISR reads (only the ring current is bound). | Observe-only machine state, a loose `StorageRing`; the rest pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The DCM crystal cut (Si(111) / Si(311)) and the energy range. | A double-crystal `Monochromator`; the crystal cut and range pending. | The monochromator Asset. |
| OPT-1 | Nice-to-have | The focusing-mirror pair (HFM / VFM) and harmonic-rejection mirror (DHRM) coatings and bend mechanisms. | Bendable focusing + harmonic-rejection mirrors bound to `Mirror`; coatings pending. | The mirror Asset detail. |
| OPT-2 | Nice-to-have | The front-end slit blade-axis map, and the secondary-source (SSA) slit (defined but commented out in source). | A front-end `Slit`; the SSA carried as a deferred gap. | The slit Asset detail. |
| ATTN-1 | Nice-to-have | The four-foil attenuator bank (bit-encoded transmission level) and its calibration. | The foils bound to `Filter`. | The attenuator Asset. |

## Detection

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The Eiger 1M model and the write path (a commissioning `testing/` path in source), and the flux monitors (the QuadEM electrometers are defined but commented out; there is no point / scaler detector for diffraction counting). | One `Camera` Asset (Eiger 1M); no `FluxMonitor` Asset modelled until the electrometers are live. | The detector and flux-monitor modelling. |
| DIAG-1 | Nice-to-have | The diagnostic screen cameras and the motorized beam-position monitor (only its stage motors are bound; the electrometers are commented out), and the position-versus-intensity split (the fleet-wide question). | `Camera` for the screens; a loose `BeamPositionMonitor` for the BPM stage (held under review). | The diagnostic modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the profile collection current and correct, and is the profile representative of production (the databroker catalog is a placeholder name and several devices are commented out, both commissioning signals)? | The handles in the descriptor are taken from the profile collection and carried confirm; the data plane (bluesky-queueserver + Tiled) is the seam CORA's edge replaces. | Verifying each Asset's control handle and the data plane. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals and the photon / front-end shutters (no PSS / shutter / hutch-interlock device is in the profile collection). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent (the optics) and the cooling supply. | Photon beam, cooling water, and vacuum on the optics. | The Supply observations. |
| GOV-1 | Nice-to-have | The NSLS-II operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the NSLS-II Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Do resonant scattering and surface (CTR) diffraction enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the 4-ID / CSX `resonant_scattering` and 4-ID / 8-ID `diffraction` Methods; doubly deferred because the diffractometer is absent from source (DIFF-1). | The technique Capabilities. |
