# P07

*PETRA III's high-energy materials-science beamline (HEMS), and CORA's eleventh PETRA III beamline. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `P07` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PETRA III (DESY)](../petra-iii/index.md) (bound via `facility_code = "petra-iii"`, `FacilityKind = Site`) |
| Sector | `P07` (the PETRA III beamline name; not a registered Asset) |
| Operator | Jointly operated by Helmholtz-Zentrum Hereon (2/3) and DESY (1/3) (`OPERATOR-1`) |
| Status | First cut, reverse-engineered, operating beamline (the optics + the EH2 and EH2B experiment hutches; scenarios deferred) |
| Source | An undulator for high-energy hard X-ray materials science |
| Control stack | PETRA III Tango device floor + Sardana scan layer; per-beamline device handles read from the public OnlineXML registry, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from P07's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p07](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p07), branch `debian/jessie`) and a verified research brief. The registry carries real Tango device names and control handles, but no crystal cuts, magnet field, energy calibration, or physical positions; those are open questions. The experiment motor banks are grouped (per-axis roles not labelled). Every value is carried as `confirm` until P07 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes P07 different

P07 "High Energy Materials Science (HEMS)" is **CORA's eleventh PETRA III beamline** and the facility's high-energy hard X-ray materials-science beamline, **jointly operated by Helmholtz-Zentrum Hereon (2/3) and DESY (1/3)** (`OPERATOR-1`). Its science is high-energy diffraction and imaging for engineering / materials studies, including a 17 T high-field magnet endstation.

P07 coins **no new Family**. It reuses the graduated catalog `Magnet` Family (earned across 4-ID + i10-1 + ID32, of which P07's 17 T magnet is a further consumer). The four-circle Eulerian diffractometer and two-theta arm bind the catalog `Goniometer` Family (not the composed `Diffractometer` Assembly, the P01 EH2 call); the multi-bounce DCM binds `Monochromator`; the hexapod `Hexapod`; the Linkam stage `TemperatureController`; the detectors `Camera` / `EnergyDispersiveSpectrometer`. The techniques (high-energy diffraction, high-field materials science) reuse the pending `diffraction` / `magnetic_scattering` slugs (`TECH-1`).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics hutch (`p07-oh2`) | Yes | The undulator, the multi-bounce DCM, the OH z-stage, the slits |
| EH2 main hutch (`p07-eh2`) | Yes | The four-circle diffractometer, the hexapod, the 17 T magnet, the Linkam, the detectors |
| EH2B secondary hutch (`p07-eh2b`) | Yes | The secondary sample bank |
| The per-axis roles of the motor banks | Grouped, not resolved | `exp*`, `oh*` not labelled per axis; grouped (`GROUP-1`) |
| The other P07 hutches (EH1 / EH3 / EH4) | Not in this slice | Only the EH2 registry slice is public here (`HOST-1`) |
| Tango / Sardana handles | Yes, from the registry | Read from the public OnlineXML (`CTRL-1`) |
| PSS permit signals | No | Not in the OnlineXML; carried pending, not invented (`PSS-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **An eleventh beamline at an existing Site, jointly operated.** PETRA III is already modelled; P07 adds the HEMS beamline. The Hereon / DESY joint operation is a facility-governance fact carried as a question (`OPERATOR-1`); the beamline controls are the PETRA III Tango / Sardana stack regardless.
- **No new Family.** The 17 T magnet is a further consumer of the graduated catalog `Magnet` Family; everything else binds existing catalog Families.
- **The diffractometer binds Goniometer.** The four-circle Eulerian (e4cv) + two-theta arm bind the catalog `Goniometer`, not the composed `Diffractometer` Assembly (`DIFF-1`).
- **The DCM is resolved.** Unlike most PETRA III banks, P07's multi-bounce DCM axes are named (`dcm_1st_*`, `dcm_2nd_*`), so the monochromator is modelled with resolved axes.

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the undulator, the multi-bounce DCM, the slits.
- [Sample](equipment/sample.md): the EH2 diffractometer + hexapod + magnet + Linkam, the EH2B sample bank.
- [Detector](equipment/detector.md): the Pilatus, PerkinElmer, and MCA detectors.

Cutting across them:

- [Controls](equipment/controls.md): the PETRA III Tango floor + Sardana scan layer and the orchestration seam; handles read from the OnlineXML, carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p07/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of P07 is designed to do, as intent. High-energy diffraction and high-field materials science reuse the pending `diffraction` / `magnetic_scattering` Methods (`TECH-1`).

## Governance

[Governance](governance.md): who will act at P07 and the trust shape that gates their commands. People and agents are facility principals at the [PETRA III Site](../petra-iii/index.md); the Hereon / DESY joint operation is noted (`OPERATOR-1`).

## Model

[Model](model.md): the developer's by-kind index, P07's place as the Hereon-operated HEMS beamline, and the record of what is deliberately deferred.

## Not yet documented

P07 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals are not in the OnlineXML and are not invented here (`PSS-1`).
