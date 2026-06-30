# P06

*PETRA III's hard X-ray micro- and nano-probe beamline, and CORA's third PETRA III beamline. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `P06` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PETRA III (DESY)](../petra-iii/index.md) (bound via `facility_code = "petra-iii"`, `FacilityKind = Site`) |
| Sector | `P06` (the PETRA III beamline name; not a registered Asset) |
| Status | First cut, reverse-engineered, operating beamline (the optics + the micro- and nano-probe endstations; scenarios deferred) |
| Source | An undulator delivering hard X-rays for scanning micro / nano fluorescence and diffraction |
| Control stack | PETRA III Tango device floor + Sardana scan layer; per-beamline device handles read from the public OnlineXML registry, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from P06's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p06](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p06), branch `debian/jessie`) and a verified research brief. The registry carries real Tango device names and control handles, but no focal sizes, energy ranges, detector models, or physical positions; those are open questions. The registry exposes large generically-named motor banks (`mi_mot01..84`, `nat_mot01..32`, the `mono_mot` bank) whose per-axis roles are not labelled, grouped here as the sample / instrument stages of their endstation. Every value is carried as `confirm` until P06 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes P06 different

P06 "Micro- and Nanoprobe" is **CORA's third PETRA III beamline** and the fleet's most complete **scanning-probe instrument**. Its science is hard X-ray scanning micro / nano fluorescence and diffraction microscopy and nano-tomography: a focused beam rastered across a sample while a high-rate XRF array and area detectors read each point. It carries two endstations: a micro-probe (MC01) and a nano-probe (NC1), each a dense stack of hexapods, KB-lens stages, and piezo scanners.

For the modelling, P06 coins **no new Family** but exercises the catalog more fully than any prior PETRA III beamline:

- The **Maia** high-rate XRF detector array binds the catalog `EnergyDispersiveSpectrometer` (one Asset carrying its dimension / flux / sensor / interlock / logger / processing sub-devices).
- The hexapods (the MC01 six-axis hexapod, the two NC1 SmarAct KB-lens hexapods) bind `Hexapod`.
- The Aerotech fly-scan stages bind `LinearStage` and carry the continuous raster-scan role (`SCAN-1`).

The technique (scanning fluorescence / diffraction microscopy + nano-tomography) earns no new catalog Method; it reuses the pending `scanning_fluorescence_microscopy` and `tomography` slugs on the [Site](../petra-iii/index.md) (`TECH-1`).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics / mono hutch (`p06-mono`) | Yes | The undulator, the DCM, the multilayer monochromator, the optics-hutch slits, the quad BPM |
| MC01 micro-probe (`p06-mc01`) | Yes | The hexapod, the sample stage, the Aerotech scan stage, the pin alignment |
| NC1 nano-probe (`p06-nc1`) | Yes | The two KB-lens hexapods, the lens fine stages, the sample piezos, the sample rotation, the nano stages |
| The detector pool | Yes | The Maia array, Eiger / Lambda / Pilatus / PCO, the XIA fluorescence detectors |
| The per-axis roles of the motor banks | Grouped, not resolved | `mi_mot`, `nat_mot`, `mono_mot` are not labelled per axis; grouped as stage Assets (`GROUP-1`) |
| Tango / Sardana handles | Yes, from the registry | Read from the public OnlineXML; some detectors report on a bare `p06` / `petra3` host (`HOST-1`, `CTRL-1`) |
| PSS permit signals | No | Not in the OnlineXML, carried pending, not invented (`PSS-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A third beamline at an existing Site.** PETRA III is already modelled; P06 adds the scanning-probe beamline and the scanning / nano-tomography practices.
- **No new Family, but the fullest catalog reuse yet.** The Maia binds `EnergyDispersiveSpectrometer`, the hexapods `Hexapod`, the KB lens stages `Hexapod` + `PseudoAxis`, the scan stages `LinearStage`, the detectors `Camera`; the catalog is unchanged.
- **The dense motor banks are grouped, not invented.** `mi_mot01..84` (MC01), `nat_mot01..32` (NC1), and the `mono_mot` bank carry no per-axis role in the registry; they are grouped as stage Assets carrying the bank prefix, every axis role pending (`GROUP-1`).
- **The shared detectors are homed in the endstation that operates them.** The Maia and area detectors report on a bare `p06` / `petra3` host without an endstation token; per the cross-host mapping decision they are homed in the detection stage with the host flagged (`HOST-1`).

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the undulator, the mono hutch, and the two probe endstations.
- [Sample](equipment/sample.md): the MC01 hexapod and sample stage, the NC1 KB-lens hexapods and sample piezos.
- [Detector](equipment/detector.md): the Maia XRF array, the area detectors, and the fluorescence detectors.

Cutting across them:

- [Controls](equipment/controls.md): the PETRA III Tango floor + Sardana scan layer and the orchestration seam; handles read from the OnlineXML, carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p06/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of P06 is designed to do, as intent. Scanning fluorescence / diffraction microscopy and nano-tomography reuse the pending `scanning_fluorescence_microscopy` and `tomography` Methods (`TECH-1`).

## Governance

[Governance](governance.md): who will act at P06 and the trust shape that gates their commands. People and agents are facility principals at the [PETRA III Site](../petra-iii/index.md).

## Model

[Model](model.md): the developer's by-kind index, P06's place as the fleet's fullest scanning-probe deployment, and the record of what is deliberately deferred.

## Not yet documented

P06 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals and shutters are not in the OnlineXML and are not invented here (`PSS-1`).
