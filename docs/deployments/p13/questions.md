# Open questions

*What CORA needs the P13 team to confirm before the model can be trusted.*

P13 was reverse-engineered from EMBL Hamburg's own public MXCuBE HardwareObjects configuration ([github.com/mxcube/mxcubecore](https://github.com/mxcube/mxcubecore/tree/develop/mxcubecore/configuration/embl_hh_p13), `configuration/embl_hh_p13`), not from a live connection. EMBL publishes a richer config than the DESY OnlineXML, so the diffractometer and its axes are named (the experiment hutch resolves into a real `Goniometer`), but the exact geometry, the optics breakdown, and the safety / operator boundary are not in it. P13 is CORA's first EMBL Hamburg beamline and the first sub-operator on the PETRA III Site. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: an optics hutch and an experiment hutch? The split is inferred from the device prefixes and the MX layout. | A `p13-oh` optics hutch and a `p13-eh` experiment hutch. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The undulator source (the MXCuBE config exposes the energy service, not the undulator device). | An undulator beamline; the source carried pending. | The source Asset. |
| GROUP-1 | Nice-to-have | The per-axis roles of the KB mirror motions (`/P13/P13Kb.CDI/*`). | Grouped as the optics-hutch focusing stage; per-mirror Assets pending. | The Asset boundaries. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The optics breakdown: the monochromator and the KB mirrors within the focusing motions, and the aperture-size table. | Grouped `LinearStage` optics motions plus a beam-defining `Aperture`; the breakdown pending. | The optics modelling. |
| ENERGY-1 | Nice-to-have | The energy / monochromator coupling behind the `TINEEnergy` service (`/P13/Energy/P13Energy`). | A `PseudoAxis` energy service; the mono motions it drives pending. | The energy modelling. |

## Sample endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MX-1 | Blocks-build | The EMBLMiniDiff goniometer geometry (kappa range, axis offsets, the omega / kappa / centring axis assignment). | The EMBLMiniDiff bound to the graduated `Goniometer` with its named axes; the geometry carried as a question. | The MX instrument modelling. |
| OAV-1 | Nice-to-have | The on-axis viewing objective (MicrodiffZoom) magnification and the on-axis / sample-changer camera handles. | An `Objective` zoom plus `Camera` viewing; the camera handle pending. | The OAV modelling. |
| CRYO-1 | Nice-to-have | The cryostream (cooler model, sensor / setpoint handles); it is not a labelled device in the MXCuBE config. | Carried as a question; the liquid nitrogen a Supply observation, not a device. | The temperature-control modelling. |
| ROBOT-1 | Blocks-go-live | The automated sample changer (load / centre / collect / unmount loop). | A deferred sample-exchange Procedure over the spine + a Subject custody thread, not a device family; MXCuBE bookkeeping, not a device. | The sample-exchange modelling. |

## The detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector models (Eiger 16M, Pilatus 6M read from the config), their ROI modes, and the sample-to-detector geometry. | Two `Camera` area detectors plus a derived `PseudoAxis` distance; the geometry pending. | The detector modelling. |
| DIAG-1 | Nice-to-have | The beam-diagnostic service split (the BCU intensity / centring services and the pin-diode flux). | Grouped `FluxMonitor` diagnostics; the per-service split pending. | The diagnostic modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Exporter / TINE control handles per P13 device, and whether the upstream MXCuBE `develop` config matches the live beamline. | The handles read from the public MXCuBE config, carried pending; the floor is MXCuBE over Exporter + TINE. | Binding each Asset's control handle. |
| SEAM-1 | Blocks-go-live | The EMBL Hamburg control domain: MXCuBE over Exporter (microdiff) + TINE, distinct from the DESY Tango / Sardana floor. | A sub-operator control-domain within the PETRA III Site; EMBL's house style recorded on the Site. | The seam and Site modelling. |
| GOV-1 | Blocks-go-live | The EMBL Hamburg operator pool, the safety-review structure, and the boundary between the DESY-hosted ring interlock and the EMBL-operated beamline. | Carried pending on the PETRA III Site, distinct from the DESY pool; the operator / interlock boundary a question. | The governance principals. |
| PSS-1 | Blocks-go-live | The personnel-safety permit signals and the photon / front-end shutters (absent from the MXCuBE config). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cryostream liquid-nitrogen / beam supplies. | Photon beam, cooling water, vacuum, and liquid nitrogen. | The Supply observations. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Does rotation MX enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice reusing the i03 `mx_data_collection` slug; none coined. | The technique Capability. |
