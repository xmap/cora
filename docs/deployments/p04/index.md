# P04

*PETRA III's variable-polarization soft X-ray spectroscopy beamline, and CORA's second PETRA III beamline. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `P04` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PETRA III (DESY)](../petra-iii/index.md) (bound via `facility_code = "petra-iii"`, `FacilityKind = Site`) |
| Sector | `P04` (the PETRA III beamline name; not a registered Asset) |
| Status | First cut, reverse-engineered, operating beamline (the soft X-ray optics + two experiment endstations; scenarios deferred) |
| Source | A variable-polarization (APPLE-II-type) undulator delivering 250-3000 eV soft X-rays |
| Control stack | PETRA III Tango device floor + Sardana scan layer; per-beamline device handles read from the public OnlineXML registry, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from P04's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p04](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p04), branch `debian/jessie`) and a verified research brief. The registry carries real Tango device names and control handles, but no grating line densities, polarization modes, energy calibration, or physical positions; those are open questions. The registry exposes generically-named motor banks (`exp1_mot01..16`, `ps2.01..14`) whose per-axis roles are not labelled, grouped here as manipulator stages. Every value is carried as `confirm` until P04 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes P04 different

P04 "Variable Polarization XUV Beamline" is **CORA's second PETRA III beamline** and the fleet's entry into the **soft X-ray / grating-monochromator regime**. Its science is soft X-ray spectroscopy at 250-3000 eV: X-ray absorption (total electron yield via a drain-current electrometer) and photoemission, fed by an APPLE-II-type variable-polarization undulator through a plane-grating monochromator.

For the modelling, P04 introduces one genuinely new device kind and reuses everything else:

- **The grating monochromator (`OPT-1`).** P04's monochromator binds the catalog `GratingMonochromator` Family, a plane-grating monochromator, **not** the crystal `Monochromator` the hard X-ray beamlines (P01, the APS / ESRF tomography lines) use. This is CORA's first PETRA III `GratingMonochromator` deployment; the Family was introduced at NSLS-II SIX and graduated into the catalog at CSX.

Otherwise P04 coins **no new Family**: the undulator binds `InsertionDevice`, the mirrors `Mirror`, the slits `Slit`, the sample manipulators `Manipulator`, the diagnostic cameras `Camera`, the electrometers `FluxMonitor`, the motorized phosphor screens the loose `Screen`. The technique (soft X-ray spectroscopy) earns no catalog Method and is carried pending on the [Site](../petra-iii/index.md) reusing the `xas_spectroscopy` and `angle_resolved_photoemission` slugs (`TECH-1`).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Soft X-ray optics (`p04-optics`) | Yes | The undulator, the plane-grating monochromator, the three mirrors, the exit slits |
| EXP1 endstation (`p04-exp1`) | Yes | The sample manipulator, a secondary positioner, the viewing camera, the electrometer |
| EXP2 endstation (`p04-exp2`) | Yes | The exit-shutter unit, the positioner, the virtual axes, the diagnostic screens + beam-monitor cameras, the electrometer |
| The undulator polarization / row-phase axes | Named, not bound | The OnlineXML exposes the gap, not the APPLE-II row-phase axes (`SRC-1`) |
| The per-axis manipulator roles | Grouped, not resolved | The motor banks are not labelled per axis; grouped as `Manipulator` Assets (`GROUP-1`) |
| Tango / Sardana handles | Yes, from the registry | Read from the public OnlineXML; some optics report on the `haspp04exp2` host (`HOST-1`, `CTRL-1`) |
| PSS permit signals | No | Not in the OnlineXML, carried pending, not invented (`PSS-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A second beamline at an existing Site.** PETRA III is already modelled (`deployments/petra-iii/site.yaml`, the P01 scaffold); P04 adds its soft X-ray beamline and the soft X-ray practices.
- **The grating monochromator is the one notable binding.** P04's PGM binds the `GratingMonochromator` Family (the soft X-ray analog of the crystal `Monochromator`), a further consumer of the catalog Family SIX introduced and CSX graduated. No new Family is coined.
- **The optics report on the experiment host.** The undulator, PGM, mirrors, and exit slits report on the `haspp04exp2` Tango host but are logically the optics section; per the cross-host mapping decision they are homed in `p04-optics` with the host flagged (`HOST-1`).
- **The unlabelled motor banks are grouped, not invented.** `exp1_mot01..16` and `ps2.01..14` carry no per-axis role in the registry; they are grouped as `Manipulator` Assets carrying the handles, every axis role pending (`GROUP-1`).

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the undulator, the soft X-ray optics, and the two experiment endstations.
- [Sample](equipment/sample.md): the sample manipulators at EXP1 and the experiment positioners at EXP2.
- [Detector](equipment/detector.md): the drain-current electrometers, and the EXP2 diagnostic screens and beam-monitor cameras.

Cutting across them:

- [Controls](equipment/controls.md): the PETRA III Tango floor + Sardana scan layer and the orchestration seam; handles read from the OnlineXML, carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p04/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of P04 is designed to do, as intent. Soft X-ray absorption and photoemission earn no catalog Method today and are carried pending, reusing the `xas_spectroscopy` and `angle_resolved_photoemission` slugs the fleet already shares (`TECH-1`).

## Governance

[Governance](governance.md): who will act at P04 and the trust shape that gates their commands. People and agents are facility principals at the [PETRA III Site](../petra-iii/index.md).

## Model

[Model](model.md): the developer's by-kind index, P04's place as CORA's first PETRA III soft X-ray / grating-monochromator deployment, and the record of what is deliberately deferred.

## Not yet documented

P04 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals and shutters are not in the OnlineXML and are not invented here (`PSS-1`).
