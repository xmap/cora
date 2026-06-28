# Open questions

*What CORA needs the SYRMEP team to confirm before the model can be trusted.*

SYRMEP was reverse-engineered from public material (the [elettra.eu SYRMEP pages](https://www.elettra.eu/elettra-beamlines/syrmep.html), the EPJ Plus 2024 SYRMEP review, and the J. Synchrotron Rad. 2023 large-FOV paper; see [the research brief](https://github.com/xmap/cora/blob/main/research/elettra/_research_brief.md)). The hardware facts are read from those sources, but **the control handles are not in public source**: the in-house DonkiOrchestra scan engine's source location is unconfirmed and the acquisition code lives in the private `gitlab.elettra.eu` `syrmep_acquisition` group. So unlike the ID32 BLISS scaffold, the device handles in the [Inventory](inventory.md) are confirm-pending placeholders rather than read addresses. This is CORA's first Elettra Site and first Tango / DonkiOrchestra controls house-style. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: a white-beam optics zone feeding one imaging / tomography endstation, or a different layout? | A shared `syrmep-optics` zone and the `syrmep-experiment` endstation. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The bending-magnet source detail (critical energy, field across the 2.0 / 2.4 GeV modes). | A bending-magnet source (section 6); 5.59 keV critical energy and 1.45 T field at 2.4 GeV. | The source Asset detail. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The Elettra storage-ring state SYRMEP reads (the 2.0 GeV / 300 mA and 2.4 GeV modes; current, fill). | Observe-only machine state, a loose `StorageRing`; exact Tango handles pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The Si(111) DCM energy range and the authoritative bound: the EPJ Plus 2024 review states mono 10-40 keV, the elettra.eu spec still lists 9-40 keV. The Bragg / offset handles. | A `Monochromator` (Si(111), fixed-exit, 20 mm offset); energy a `PseudoAxis`; range 10-40 keV mono. | The monochromator and incident-energy Assets. |
| MODE-1 | Blocks-go-live | The mono / white (pink) beam switch: how the beam bypasses the DCM, and the white-beam energy (~16-30 keV average). | The beam mode is a per-Asset setting on the `Monochromator` (the 2-BM DMM insert/retract precedent). | The beam-mode modelling. |
| OPT-1 | Nice-to-have | The white-beam-defining mask dimensions and drawing. | A fixed `Mask` upstream of the optics. | The mask Asset detail. |
| OPT-2 | Blocks-go-live | The laminar-beam slit blade-axis map and handles, and the beam dimensions (sources cite ~120 x 4 mm at 20 m and ~160 x 5 mm at 23 m). | Slits bound to `Slit`; a ~120-160 mm wide, ~4-5 mm tall laminar beam at 7 mrad acceptance. | The slit Asset detail and beam geometry. |
| FOIL-1 | Nice-to-have | The absorption / beam-hardening filter foils and the selector handle. | Filters bound to `Filter`; foils pending. | The filter Asset detail. |

## Sample

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | The rotation stages: the heavy-payload rotator (up to 120 kg, 1-20 deg/s, 0.02 deg) is documented, but the standard sample rotation stage range / bearing / model and the rotator wobble spec are not. | A `RotaryStage` for the tomographic theta; a standard-stage variant and the wobble spec pending. | The rotation-stage modelling. |
| SAMPLE-1 | Blocks-go-live | The five-axis sample-positioning stage: motor vendors, micro-positioning resolution, axes, and handles. | A `LinearStage` facet set; vendors / resolution / axis map pending. | The sample-stage modelling. |

## Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The default routine-tomography camera and its pixel size and field of view: the sCMOS (2048x2048, 0.9-5.7 um) or the CCD (4008x2672, 4.5 um)? | Both bind `Camera`; the routine camera is pending. | The detector modelling. |
| DET-2 | Nice-to-have | The sample-to-detector propagation rail and the two-axis detector rail handles. | A `LinearStage` (range 3-160 cm). | The propagation-rail Asset. |
| DET-3 | Nice-to-have | The routine scintillator screen type and thickness (published configs cite GGG:Eu). | A `Scintillator`; type and thickness pending. | The scintillator Asset. |
| DET-4 | Nice-to-have | The XC Hydra photon-counting detector pixel size and configuration, and when it is used. | A `Camera` for the large-specimen / helical CT mode; pixel size pending. | The photon-counting detector modelling. |

## Controls and acquisition

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-build | The Tango device namespaces and the DonkiOrchestra (Elettra 2.0: "Executer") scan-engine handles: SYRMEP's control source is not public. | A Tango device floor with the in-house DonkiOrchestra scan engine; handles are confirm-pending placeholders. | The whole control plane (every device handle in the Inventory). |
| PSS-1 | Blocks-go-live | The Elettra personnel-safety permit signals and the front-end / safety shutters. | Enclosure permit leaves and a `Shutter`, carried pending, not invented. | The safety / interlock structure. |

## Techniques and compute

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | The technique scope: core tomography reuses catalog Methods, but helical CT, white-beam tomography, and phase retrieval are not yet catalog Methods. | The core tomography Practices reuse catalog Methods; the rest are pending and render unlinked. | Whether the new techniques enter the catalog (a CORA-scope call on [Model](model.md#deliberately-not-here-yet)). |
| COMPUTE-1 | Nice-to-have | The reconstruction pipeline (the SYRMEP Tomo Project: phase retrieval, ring removal, FBP / iterative on ASTRA + TomoPy) and whether CORA records its invocation as Method / Compute provenance. | Post-acquisition compute CORA records as provenance, not data it owns. | The compute-provenance modelling. |
| SUP-1 | Nice-to-have | The facility supplies a run draws on (cooling water for the optics, the vacuum extent of the white-beam path). | `PhotonBeam`, `CoolingWater`, `Vacuum`. | The Supply detail. |

## Governance

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| GOV-1 | Nice-to-have | The Elettra operator pool and safety-review structure (site-level). | Carried pending on the Elettra Site, not instantiated per beamline. | The governance principals. |
