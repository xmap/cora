# P03

*PETRA III's micro- and nanofocus small-angle X-ray scattering beamline, and CORA's fifth PETRA III beamline. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `P03` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PETRA III (DESY)](../petra-iii/index.md) (bound via `facility_code = "petra-iii"`, `FacilityKind = Site`) |
| Sector | `P03` (the PETRA III beamline name; not a registered Asset) |
| Status | First cut, reverse-engineered, operating beamline (the shared optics + microfocus and nanofocus endstations; scenarios deferred) |
| Source | An undulator delivering 9-23 keV for small- and wide-angle X-ray scattering |
| Control stack | PETRA III Tango device floor + Sardana scan layer; per-beamline device handles read from the public OnlineXML registry, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from P03's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p03](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p03), branch `debian/jessie`) and a verified research brief. The registry carries real Tango device names and control handles, but no focal sizes, multilayer d-spacing, energy calibration, or physical positions; those are open questions. The registry exposes generically-named motor banks (`expmi_mot01..64` at the microfocus endstation, `mot01..40` at the nanofocus endstation) whose per-axis roles are not labelled, grouped here as the sample stages of their endstation. Every value is carried as `confirm` until P03 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes P03 different

P03 "MiNaXS" (Micro- and Nanofocus Small-Angle X-ray Scattering) is **CORA's fifth PETRA III beamline** and the fleet's entry into **small-angle / wide-angle scattering** (SAXS / WAXS). Its science is micro- and nanofocus SAXS / WAXS at 9-23 keV across two endstations: a microfocus endstation and the nanofocus **GINIX** (Goettingen Instrument for Nano-Imaging with X-rays) endstation with its waveguide nano-focusing.

For the modelling, P03 coins **no new Family** but brings two things new to the PETRA III set:

- A **two-endstation layout** sharing one optics chain (the microfocus and the nanofocus GINIX), plus the **shared P02 / P03 high-heatload optics** (the first defining slit reports on the P02 host, `HOST-1`).
- Several **new Tango motion-controller protocols**: Galil DMC slit controllers (the guard slits) and SmarPod controllers (the GINIX waveguide), alongside the hexapod, Smaract, and OMS controllers.

The technique (SAXS / WAXS) earns no new catalog Method; it reuses the pending `small_angle_scattering` and `wide_angle_scattering` slugs on the [Site](../petra-iii/index.md) (`TECH-1`).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Shared optics (`p03-optics`) | Yes | The undulator, the multilayer monochromator, the two mirrors, the defining slits, the quad BPMs |
| Microfocus endstation (`p03-microfocus`) | Yes | The CRL hexapod, the guard slit, slit4, the sample bank, the Eurotherm, the Pilatus 300k/1M, the fluorescence detectors |
| Nanofocus GINIX (`p03-nanofocus`) | Yes | The waveguide SmarPod, the sample hexapod, the rotation, the guard slit, the sample bank, the LEDs / camera, the Pilatus, the shutter |
| The per-axis roles of the motor banks | Grouped, not resolved | `expmi_mot`, `mot` banks not labelled per axis; grouped as stage Assets (`GROUP-1`) |
| Tango / Sardana handles | Yes, from the registry | Read from the public OnlineXML; the first slit + a Lambda report on other hosts (`HOST-1`, `CTRL-1`) |
| PSS permit signals | No | Not in the OnlineXML, carried pending, not invented (`PSS-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A fifth beamline at an existing Site.** PETRA III is already modelled; P03 adds the SAXS / WAXS beamline and the scattering practices, completing the four-pick batch (P04, P06, P11, P03).
- **No new Family.** The monochromator binds `Monochromator`, the mirrors `Mirror`, the CRL and GINIX hexapods `Hexapod`, the slits `Slit`, the rotation `RotaryStage`, the detectors `Camera` / `EnergyDispersiveSpectrometer`, the cryo / heater `TemperatureController`, the shutter `Shutter`; the catalog is unchanged.
- **Shared P02 / P03 optics are homed in the P03 optics enclosure.** The first defining slit reports on the P02 host (`haspp02oh1`); per the cross-host mapping decision it is homed in `p03-optics` with the host flagged (`HOST-1`).
- **The motor banks are grouped, not invented.** `expmi_mot01..64` (microfocus) and `mot01..40` (nanofocus) carry no per-axis role in the registry; grouped as sample-stage Assets, roles pending (`GROUP-1`).

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the undulator, the shared optics, and the two endstations.
- [Sample](equipment/sample.md): the microfocus CRL + sample stage, the nanofocus GINIX waveguide + sample hexapod + rotation.
- [Detector](equipment/detector.md): the Pilatus detectors and the fluorescence detectors at both endstations.

Cutting across them:

- [Controls](equipment/controls.md): the PETRA III Tango floor + Sardana scan layer and the orchestration seam; handles read from the OnlineXML, carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p03/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of P03 is designed to do, as intent. SAXS and WAXS reuse the pending `small_angle_scattering` and `wide_angle_scattering` Methods (`TECH-1`).

## Governance

[Governance](governance.md): who will act at P03 and the trust shape that gates their commands. People and agents are facility principals at the [PETRA III Site](../petra-iii/index.md).

## Model

[Model](model.md): the developer's by-kind index, P03's place as PETRA III's first SAXS / WAXS beamline, and the record of what is deliberately deferred.

## Not yet documented

P03 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals and shutters are not in the OnlineXML and are not invented here (`PSS-1`).
