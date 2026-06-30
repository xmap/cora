# P13

*EMBL Hamburg's macromolecular-crystallography beamline on the PETRA III ring, and CORA's first EMBL Hamburg beamline. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `P13` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PETRA III (DESY)](../petra-iii/index.md) (bound via `facility_code = "petra-iii"`, `FacilityKind = Site`) |
| Operator | EMBL Hamburg (a sub-operator control-domain within the PETRA III Site, `SEAM-1`) |
| Sector | `P13` (the PETRA III beamline name; not a registered Asset) |
| Status | First cut, reverse-engineered, operating beamline (the optics + experiment hutch; scenarios deferred) |
| Source | An undulator for macromolecular crystallography |
| Control stack | EMBL Hamburg's own domain: MXCuBE over the Exporter protocol (microdiff host) + TINE channels, carried confirm (`CTRL-1`), distinct from the DESY Tango / Sardana floor |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from EMBL Hamburg's own public MXCuBE HardwareObjects configuration ([github.com/mxcube/mxcubecore](https://github.com/mxcube/mxcubecore/tree/develop/mxcubecore/configuration/embl_hh_p13), `configuration/embl_hh_p13`), the device topology MXCuBE drives at the beamline. Device logical names and control handles are read from it and carried as `confirm` until P13 staff verify them. The config sees device motions and services, not the optic Assets themselves, so the monochromator and KB mirror structure are grouped and carried as questions. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes P13 different

P13 is **CORA's first EMBL Hamburg beamline**, and the first beamline CORA models that sits on the PETRA III ring but is **not operated by DESY**. EMBL Hamburg runs three beamlines on the ring (P12 BioSAXS, P13 and P14 macromolecular crystallography); P13 is its high-throughput single-position MX beamline. Its science is rotation MX: a crystal mounted on the EMBLMiniDiff microdiffractometer, cryo-cooled, rotated through an oscillation while an Eiger or Pilatus area detector reads frames.

The distinctive fact is the **sub-operator seam**. P13 shares the PETRA III Site and Facility with the DESY beamlines (P01 / P06 / P11), but it does **not** run DESY's Tango / Sardana / OnlineXML house style. EMBL Hamburg has its own control domain: MXCuBE as the experiment-orchestration layer, over the Exporter protocol (the microdiff host, `p13md201.embl-hamburg.de:9001`) and TINE channels (`/P13/...`) for the detector, energy, and beam services. So P13 is modelled as a **sub-operator control-domain within the PETRA III Site**: same ring and Facility, distinct operator and control floor (`SEAM-1`).

For the modelling, P13 is a **reuse-and-reinforce** deployment: it coins no new vocabulary. It is the seventh MX beamline CORA models (after Diamond i03, NSLS-II FMX / AMX, the Australian Synchrotron MX3, Sirius MANACA, NSRRC TPS 07A / 05A, and DESY P11), and it reuses the MX vocabulary directly:

- The EMBLMiniDiff binds the graduated `Goniometer`; the Eiger / Pilatus detectors bind `Camera`; the XRF detector binds `EnergyDispersiveSpectrometer`; the aperture / beamstop / objective / lights / shutters bind the matching catalog Families.
- The MX technique reuses the pending i03 `mx_data_collection` Method (`TECH-1`).

The honest gain over P11: because EMBL publishes the MXCuBE config (which names the diffractometer, its kappa axes, the aperture, the beamstop, the detectors by model), P13's experiment hutch resolves into a real `Goniometer` instrument rather than the area-grouped motor banks the sparser DESY OnlineXML forced at P11.

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics hutch (`p13-oh`) | Grouped | The KB mirror pitch / roll motions; the mirror / mono Assets are not labelled (`OPT-1`) |
| Experiment hutch (`p13-eh`) | Yes | The EMBLMiniDiff diffractometer, its centring / kappa axes, the aperture / beamstop / objective / lights |
| The detectors | Yes | The Eiger 16M and Pilatus 6M area detectors, the flux monitor, the XRF detector |
| The diffractometer / MX instrument | Resolved | The MXCuBE config names the EMBLMiniDiff and its axes; bound to `Goniometer` (`MX-1`) |
| The sample-changer robot | Not modelled | The MXCuBE sample-changer logic is bookkeeping, not a device; a deferred sample-exchange Procedure (`ROBOT-1`) |
| MXCuBE / Exporter / TINE handles | Yes, from the config | Read from the public MXCuBE config; carried confirm (`CTRL-1`, `SEAM-1`) |
| PSS permit signals | No | Not in the MXCuBE config, carried pending, not invented (`PSS-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A sub-operator at an existing Site.** PETRA III is already modelled; P13 adds the first EMBL Hamburg beamline as a distinct control-domain within the Site, with EMBL's house style recorded in the [PETRA III Site](../petra-iii/index.md) descriptor (`SEAM-1`).
- **A reuse-and-reinforce MX deployment.** P13 coins no new Family and no new Method: it reuses the MX vocabulary (the `Goniometer` diffractometer, the `Camera` detectors) and the pending i03 `mx_data_collection` Method, the same as MANACA, TPS 07A, and P11.
- **The diffractometer resolves.** Unlike P11's sparse OnlineXML, EMBL's MXCuBE config names the EMBLMiniDiff and its omega / kappa / centring axes, so the experiment hutch is modelled as a real `Goniometer` instrument (`MX-1`).
- **Two control protocols, one domain.** The microdiff motions are Exporter-hosted; the detector / energy / beam services are TINE channels. Both are read from the MXCuBE config and carried confirm (`CTRL-1`).

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the KB mirror focusing stage, the energy axis, and the beam diagnostics.
- [Sample](equipment/sample.md): the EMBLMiniDiff diffractometer, its centring stage, the aperture / beamstop / objective / illumination.
- [Detector](equipment/detector.md): the Eiger and Pilatus area detectors, the flux monitor, the cameras, and the XRF detector.

Cutting across them:

- [Controls](equipment/controls.md): EMBL Hamburg's MXCuBE + Exporter + TINE domain and the orchestration seam; handles read from the MXCuBE config, carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p13/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of P13 is designed to do, as intent. Rotation MX reuses the pending `mx_data_collection` Method (`TECH-1`).

## Governance

[Governance](governance.md): who will act at P13 and the trust shape that gates their commands. People and agents are facility principals at the [PETRA III Site](../petra-iii/index.md); the EMBL Hamburg operator structure is carried pending and distinct from the DESY pool (`GOV-1`).

## Model

[Model](model.md): the developer's by-kind index, P13's place as CORA's first EMBL Hamburg beamline, and the record of what is deliberately deferred.

## Not yet documented

P13 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals and shutters are not in the MXCuBE config and are not invented here (`PSS-1`).
