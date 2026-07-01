# P09

*PETRA III's resonant-scattering, diffraction, and magnetism beamline, and CORA's seventh PETRA III beamline. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `P09` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PETRA III (DESY)](../petra-iii/index.md) (bound via `facility_code = "petra-iii"`, `FacilityKind = Site`) |
| Sector | `P09` (the PETRA III beamline name; not a registered Asset) |
| Status | First cut, reverse-engineered, operating beamline (the resonant-scattering, diffraction, and magnetism areas; scenarios deferred) |
| Source | An undulator delivering hard X-rays for resonant scattering, diffraction, and magnetism |
| Control stack | PETRA III Tango device floor + Sardana scan layer; per-beamline device handles read from the public OnlineXML registry, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from P09's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p09](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p09), branch `debian/jessie`) and a verified research brief. The registry carries real Tango device names and control handles, but no crystal cuts, magnet field, energy calibration, or physical positions; those are open questions. The registry exposes generically-named motor banks (the MONO and DIF `p09/motor` banks) whose per-axis roles are not labelled, grouped here as the optics / endstation stages. Every value is carried as `confirm` until P09 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes P09 different

P09 "Resonant Scattering and Diffraction" is **CORA's seventh PETRA III beamline** and the richest of the PETRA III set in technique breadth: resonant elastic X-ray scattering and HAXPES in the MONO hutch, diffraction in the DIF hutch, and high-field magnetism (XMCD, magnetic scattering) in the MAG endstation with a 14 T superconducting magnet.

For the modelling, P09 coins **no new Family** but exercises the polarization / magnetism vocabulary the APS 4-ID deployment introduced. It reuses the catalog `PhaseRetarder` Family (P09 is the second consumer, part of the 4-ID / P09 / P22 rule-of-three) and two allowlisted-loose Families:

- `PhaseRetarder` (the polarization phase-retarder circles, a catalog Family, `POL-1`),
- `PolarizationAnalyzer` (the scattered-beam analyzer, allowlisted-loose, `POL-2`),
- `Magnet` (the 14 T sample-environment magnet, allowlisted-loose, `MAG-1`).

The diffractometer circles bind the catalog `Goniometer` Family (not the composed `Diffractometer` Assembly, the same call as P01 EH2, `DIFF-1`). The techniques (resonant scattering, magnetic scattering, XMCD) earn no catalog Method; they reuse the pending `resonant_scattering` / `magnetic_scattering` / `xmcd` slugs the 4-ID / i06 / i10 beamlines already share (`TECH-1`).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| MONO hutch (`p09-mono`) | Yes | The undulator, the DCM, the mirrors, the CRL, the slit, the resonant-scattering instrument (phase retarder / analyzer / goniometer / PerkinElmer), the fluorescence detectors |
| DIF hutch (`p09-dif`) | Yes | The diffractometer goniometer and the sample bank |
| MAG endstation (`p09-mag`) | Yes | The 14 T magnet, the goniometer, the hexapod, the piezos, the analyzer, the detectors |
| The per-axis roles of the motor banks | Grouped, not resolved | The MONO / DIF `p09/motor` banks not labelled per axis; grouped as stage Assets (`GROUP-1`) |
| Tango / Sardana handles | Yes, from the registry | Read from the public OnlineXML; a Lambda + a P07 device row are flagged / excluded (`HOST-1`) |
| PSS permit signals | No | Not in the OnlineXML; carried pending, not invented (`PSS-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A seventh beamline at an existing Site.** PETRA III is already modelled; P09 adds the resonant-scattering / magnetism beamline and its practices.
- **The 4-ID vocabulary ports cleanly.** P09 reuses the catalog `PhaseRetarder` Family (the second consumer, part of the 4-ID / P09 / P22 rule-of-three) plus the allowlisted-loose `PolarizationAnalyzer` and `Magnet` Families that the APS 4-ID deployment introduced, the second consumer of each. No new Family is coined.
- **The diffractometer circles bind Goniometer.** The MONO / DIF / MAG six-circle (E6C) diffractometers bind the catalog `Goniometer` Family, not the composed `Diffractometer` Assembly, until the full circle / detector-arm structure is confirmed (`DIFF-1`).
- **The SIS3302 ROI explosion is grouped.** The SIS3302 fluorescence digitizer is exposed as many ROI sub-channels in the registry; grouped here as one `EnergyDispersiveSpectrometer` Asset (`DET-1`). A stray `p07/hexapodsmall` row (a P07 device imported into the P09 registry) is excluded (`HOST-1`).

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the undulator, the MONO-hutch optics, and the three areas.
- [Sample](equipment/sample.md): the MONO resonant-scattering instrument, the DIF goniometer, the MAG magnet + goniometer + hexapod.
- [Detector](equipment/detector.md): the PerkinElmer, Pilatus, Andor, SIS3302, and MCA detectors.

Cutting across them:

- [Controls](equipment/controls.md): the PETRA III Tango floor + Sardana scan layer and the orchestration seam; handles read from the OnlineXML, carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p09/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of P09 is designed to do, as intent. Resonant scattering, magnetic scattering, and XMCD reuse the pending `resonant_scattering` / `magnetic_scattering` / `xmcd` Methods (`TECH-1`).

## Governance

[Governance](governance.md): who will act at P09 and the trust shape that gates their commands. People and agents are facility principals at the [PETRA III Site](../petra-iii/index.md).

## Model

[Model](model.md): the developer's by-kind index, P09's place as the second consumer of the 4-ID polarization / magnetism vocabulary, and the record of what is deliberately deferred.

## Not yet documented

P09 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals are not in the OnlineXML and are not invented here (`PSS-1`).
