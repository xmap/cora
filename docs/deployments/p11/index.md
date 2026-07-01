# P11

*PETRA III's bio-imaging and macromolecular-crystallography beamline, and CORA's fourth PETRA III beamline. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `P11` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PETRA III (DESY)](../petra-iii/index.md) (bound via `facility_code = "petra-iii"`, `FacilityKind = Site`) |
| Sector | `P11` (the PETRA III beamline name; not a registered Asset) |
| Status | First cut, reverse-engineered, operating beamline (the optics + experiment hutch; scenarios deferred) |
| Source | An undulator for high-throughput macromolecular crystallography and bio-imaging |
| Control stack | PETRA III Tango device floor + Sardana scan layer; per-beamline device handles read from the public OnlineXML registry, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from P11's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p11](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p11), branch `debian/jessie`) and a verified research brief. The P11 registry is sparser in labelling than the other PETRA III beamlines: most of its devices are area-grouped motor banks (`oh_mot*`, `granite_mot*`, `eh1/eh2/eh3_mot*`, the piezomotor bank) whose per-axis roles are not exposed, so the goniometer and the MX-specific instruments are not individually resolvable from the registry and the Asset grouping leans on the area prefixes. Every value is carried as `confirm` until P11 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes P11 different

P11 "Bio-Imaging and Diffraction" is **CORA's fourth PETRA III beamline** and PETRA III's first **macromolecular-crystallography** beamline. Its science is high-throughput rotation MX (a crystal mounted on a goniometer rotated through an oscillation while a Pilatus area detector reads frames, with cryostream cooling) plus coherent / full-field bio-imaging.

For the modelling, P11 is a **reuse-and-reinforce** deployment: it coins no new vocabulary. It is a further MX beamline CORA models (after Diamond i03, NSLS-II FMX / AMX, the Australian Synchrotron MX3, Sirius MANACA, and NSRRC TPS 07A / 05A), and it reuses the MX vocabulary directly:

- The cryostream binds the graduated `TemperatureController`; the area detector binds `Camera`; the fluorescence detector binds `EnergyDispersiveSpectrometer`.
- The MX technique reuses the pending i03 `mx_data_collection` Method; the bio-imaging reuses the catalog `tomography` Method (`TECH-1`).

The honest limitation: unlike the other PETRA III beamlines, P11's registry does not label its goniometer or sample changer, so this cut models the experiment hutch as area-grouped positioning stages with the MX structure carried as a question (`MX-1`), rather than a fully-resolved MX instrument.

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics hutch (`p11-oh`) | Yes | The oh and granite motor banks (the conditioning optics, grouped) |
| Experiment hutch (`p11-eh`) | Yes | The eh1 / eh2 / eh3 / piezo motor banks, the servo, the cryostream |
| The detectors | Yes | The Pilatus area detector and the XIA fluorescence detector |
| The goniometer / MX instrument | Grouped, not resolved | The registry does not label a goniometer; the eh banks are grouped (`MX-1`, `GROUP-1`) |
| The sample-changer robot | Not modelled | Not in the registry; would be a deferred sample-exchange Procedure (`ROBOT-1`) |
| Tango / Sardana handles | Yes, from the registry | Read from the public OnlineXML; one host (`haspp11oh`) for the whole beamline (`ENC-1`, `CTRL-1`) |
| PSS permit signals | No | Not in the OnlineXML, carried pending, not invented (`PSS-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A fourth beamline at an existing Site.** PETRA III is already modelled; P11 adds the MX / bio-imaging beamline and the MX / imaging practices.
- **A reuse-and-reinforce MX deployment.** P11 coins no new Family and no new Method: it reuses the MX vocabulary (the `TemperatureController` cryostream, the `Camera` detector) and the pending i03 `mx_data_collection` Method, the same as MANACA and TPS 07A.
- **The experiment hutch is grouped honestly.** The registry does not label the goniometer or sample changer; the eh1 / eh2 / eh3 banks are grouped as experiment-hutch positioning stages, with the MX instrument structure carried as a question (`MX-1`) rather than invented.
- **One Tango host, inferred enclosures.** The whole beamline reports on `haspp11oh`; the optics / experiment hutch split is inferred from the device-name prefixes and carried confirm (`ENC-1`).

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the optics-hutch and granite stages.
- [Sample](equipment/sample.md): the experiment-hutch positioning stages, the servo, and the cryostream.
- [Detector](equipment/detector.md): the Pilatus area detector and the XIA fluorescence detector.

Cutting across them:

- [Controls](equipment/controls.md): the PETRA III Tango floor + Sardana scan layer and the orchestration seam; handles read from the OnlineXML, carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p11/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of P11 is designed to do, as intent. Rotation MX and bio-imaging reuse the pending `mx_data_collection` and `tomography` Methods (`TECH-1`).

## Governance

[Governance](governance.md): who will act at P11 and the trust shape that gates their commands. People and agents are facility principals at the [PETRA III Site](../petra-iii/index.md).

## Model

[Model](model.md): the developer's by-kind index, P11's place as PETRA III's first MX beamline, and the record of what is deliberately deferred.

## Not yet documented

P11 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals and shutters are not in the OnlineXML and are not invented here (`PSS-1`).
