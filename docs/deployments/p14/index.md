# P14

*EMBL Hamburg's high-end macromolecular-crystallography beamline on the PETRA III ring, the sibling of P13, and CORA's first two-endstation MX beamline. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `P14` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PETRA III (DESY)](../petra-iii/index.md) (bound via `facility_code = "petra-iii"`, `FacilityKind = Site`) |
| Operator | EMBL Hamburg (a sub-operator control-domain within the PETRA III Site, `SEAM-1`) |
| Sector | `P14` (the PETRA III beamline name; not a registered Asset) |
| Status | First cut, reverse-engineered, operating beamline (the optics hutch + two experiment hutches; scenarios deferred) |
| Source | An undulator for macromolecular crystallography |
| Control stack | EMBL Hamburg's own domain: MXCuBE over the Exporter protocol (microdiff hosts) + TINE channels, carried confirm (`CTRL-1`), distinct from the DESY Tango / Sardana floor |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from EMBL Hamburg's own public MXCuBE HardwareObjects configuration ([github.com/mxcube/mxcubecore](https://github.com/mxcube/mxcubecore/tree/develop/mxcubecore/configuration/embl_hh_p14), `configuration/embl_hh_p14` for EH1 and `configuration/embl_hh_pe2` for EH2), the device topology MXCuBE drives at the beamline. Device logical names and control handles are read from it and carried as `confirm` until P14 staff verify them. Some EH2 axes are published as `MotorMockup` (a simulation placeholder), so the EH2 motions are carried with extra caution (`MOCK-1`). What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes P14 different

P14 is **CORA's second EMBL Hamburg beamline** (the sibling of [P13](../p13/index.md)) and the **first two-endstation MX beamline** CORA models. Like P13 it is operated by EMBL Hamburg on the PETRA III ring, not by DESY, and it runs the same EMBL control domain (MXCuBE over Exporter + TINE). Its science is high-end rotation MX, including high-energy data collection on CdTe-sensor detectors and in-situ X-ray imaging.

The distinctive fact is the **two experiment hutches fed by one source**. Where P13 has a single hutch, P14's optics chain (the KB mirrors, the CRL transfocator, the beam-defining slits, the shared photon energy) feeds two experiment hutches:

- **EH1**: the main MX endstation, the EMBLMiniDiff microdiffractometer (hosts `p14md301` / `p14md302`) with three Eiger detector variants (a 16M silicon and 16M / 4M CdTe high-energy variants) and an X-ray imaging camera.
- **EH2**: a second endstation, the EMBLBSD diffractometer (host `pe2bsd01`) with a Pilatus 2M, fed by the same P14 energy and primary CRL.

EMBL publishes EH1 and EH2 as two MXCuBE configs (`embl_hh_p14`, `embl_hh_pe2`); this cut models both, with three enclosures (one optics hutch, two experiment hutches) (`EH-1`).

For the modelling, P14 is a **reuse-and-reinforce** deployment: it coins no new vocabulary. It is the eighth MX beamline CORA models (after Diamond i03, NSLS-II FMX / AMX, MX3, MANACA, TPS 07A / 05A, DESY P11, and EMBL P13), and it reuses the MX vocabulary directly:

- The EMBLMiniDiff and EMBLBSD bind the graduated `Goniometer`; the Eiger / Pilatus detectors bind `Camera`; the XRF detector binds `EnergyDispersiveSpectrometer`; the CRL binds `Transfocator`; the slits bind `Slit`; the focusing mirror binds `Mirror`.
- The MX technique reuses the pending i03 `mx_data_collection` Method (`TECH-1`).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics hutch (`p14-oh`) | Yes | The KB mirror motions, the CRL transfocator, the beam-defining slits, shared by both hutches |
| Experiment hutch 1 (`p14-eh1`) | Yes | The EMBLMiniDiff, the three Eiger detectors, the XRF detector, the X-ray imaging camera |
| Experiment hutch 2 (`p14-eh2`) | Yes | The EMBLBSD diffractometer, the Pilatus 2M, the EH2 table and beam-defining optics |
| The diffractometers | Resolved | The MXCuBE configs name the EMBLMiniDiff and EMBLBSD; both bound to `Goniometer` (`MX-1`) |
| The EH2 motions | Modelled with caution | Some EH2 axes are `MotorMockup` in the config (simulation placeholders) (`MOCK-1`) |
| The sample-changer robot | Not modelled | MXCuBE bookkeeping, not a device; a deferred sample-exchange Procedure (`ROBOT-1`) |
| MXCuBE / Exporter / TINE handles | Yes, from the configs | Read from the public MXCuBE configs; carried confirm (`CTRL-1`, `SEAM-1`) |
| PSS permit signals | No | Not in the MXCuBE configs, carried pending, not invented (`PSS-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A second EMBL Hamburg beamline at an existing Site.** P14 reuses the EMBL sub-operator control-domain established for P13 on the [PETRA III Site](../petra-iii/index.md) (`SEAM-1`); it adds no new Site-level house style.
- **Two experiment hutches, one source.** The optics chain feeds EH1 and EH2; the energy and CRL services are shared, each hutch carries its own diffractometer host. Modelled as three enclosures under one root Asset (`EH-1`).
- **A reuse-and-reinforce MX deployment.** P14 coins no new Family and no new Method: it reuses the MX vocabulary and the pending i03 `mx_data_collection` Method, the same as P13.
- **The EH2 mockups are flagged, not hidden.** The published EH2 config carries `MotorMockup` axes; rather than present them as live, they are carried with a caution marker (`MOCK-1`).

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the KB focusing stage, the focusing mirror, the CRL transfocator, the beam-defining slits, the energy axis, and the beam diagnostics.
- [Sample](equipment/sample.md): the EH1 EMBLMiniDiff and the EH2 EMBLBSD diffractometers, their apertures / beamstops / objectives / illumination, and the EH2 table.
- [Detector](equipment/detector.md): the EH1 Eiger variants and X-ray imaging, the EH2 Pilatus 2M, the flux monitor, the cameras, and the XRF detector.

Cutting across them:

- [Controls](equipment/controls.md): EMBL Hamburg's MXCuBE + Exporter + TINE domain and the orchestration seam; handles read from the MXCuBE configs, carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p14/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of P14 is designed to do, as intent. Rotation MX reuses the pending `mx_data_collection` Method (`TECH-1`).

## Governance

[Governance](governance.md): who will act at P14 and the trust shape that gates their commands. People and agents are facility principals at the [PETRA III Site](../petra-iii/index.md); the EMBL Hamburg operator structure is carried pending and shared with P13 (`GOV-1`).

## Model

[Model](model.md): the developer's by-kind index, P14's place as CORA's first two-endstation MX beamline, and the record of what is deliberately deferred.

## Not yet documented

P14 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals and shutters are not in the MXCuBE configs and are not invented here (`PSS-1`).
