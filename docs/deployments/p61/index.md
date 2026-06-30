# P61

*PETRA III's high-energy white-beam wiggler beamline, and CORA's seventeenth PETRA III beamline (the last with a public OnlineXML registry). This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `P61` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PETRA III (DESY)](../petra-iii/index.md) (bound via `facility_code = "petra-iii"`, `FacilityKind = Site`) |
| Sector | `P61` (the PETRA III beamline name; not a registered Asset) |
| Status | First cut, reverse-engineered, operating beamline (the experiment motor bank; scenarios deferred) |
| Source | A damping wiggler delivering high-energy white beam |
| Control stack | PETRA III Tango device floor + Sardana scan layer; per-beamline device handles read from the public OnlineXML registry, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from P61's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p61](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p61), branch `debian/stretch`, the only PETRA III extras package on the stretch branch) and a verified research brief. The P61 registry is thin: it exposes one large generic motor bank (`eh_mot*`) whose per-axis roles are not labelled, and the source, the Large Volume Press, and the detectors are not exposed. Every value is carried as `confirm` until P61 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes P61 different

P61 "High Energy Wiggler Beamline" is **CORA's seventeenth PETRA III beamline** and the facility's high-energy white-beam beamline, fed by a damping wiggler. It runs **P61A** (Large Volume Press, high-pressure / high-temperature in-situ studies) and **P61B** (high-energy white-beam / engineering energy-dispersive diffraction). It is the last PETRA III beamline with a public OnlineXML registry, completing CORA's OnlineXML-driven coverage of the facility.

P61 is a thin **reuse-and-reinforce** scaffold: it coins no new vocabulary. The motor bank binds `LinearStage`, the technique reuses the pending `energy_dispersive_diffraction` slug (`TECH-1`), and the energy-dispersive detector is carried as a pending `EnergyDispersiveSpectrometer` placeholder (`DET-1`). The Large Volume Press, if exposed, would reuse the allowlisted-loose `PressureCell` Family (the 13-id-d / P02 precedent); it is not in this registry slice and is carried pending (`PRESS-1`).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Experiment hutch (`p61-eh2`) | Yes | The experiment / instrument motor bank (grouped) |
| The source (damping wiggler) | Pending | Not exposed in this registry slice (`SRC-1`) |
| The Large Volume Press (P61A) | Pending | Not exposed in this registry slice (`PRESS-1`) |
| The detectors | Pending placeholder | Not exposed in this registry slice (`DET-1`) |
| The per-axis bank roles | Grouped, not resolved | The `eh_mot*` bank not labelled (`GROUP-1`) |
| PSS permit signals | No | Not in the OnlineXML; carried pending, not invented (`PSS-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A seventeenth beamline at an existing Site, modelled thinly.** PETRA III is already modelled; P61 adds the high-energy white-beam beamline and its practice. The sparse registry slice (one generic bank, on the unusual `debian/stretch` branch) means a thin model with the source / press / detectors carried pending, the model-what-the-source-supports posture.
- **No new Family.** The motor bank binds `LinearStage`; the catalog is unchanged.
- **The wiggler source.** P61 is a damping-wiggler beamline (`source: superconducting-wiggler`); the wiggler parameters are not in the registry and are carried pending (`SRC-1`).
- **The Large Volume Press is named, not bound.** P61A's press would reuse the allowlisted-loose `PressureCell` Family (P02 precedent) when exposed; carried pending (`PRESS-1`).

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the experiment / instrument motor bank.
- [Sample](equipment/sample.md): the experiment stage (grouped); the Large Volume Press (pending).
- [Detector](equipment/detector.md): the energy-dispersive detector (carried pending).

Cutting across them:

- [Controls](equipment/controls.md): the PETRA III Tango floor + Sardana scan layer and the orchestration seam; handles read from the OnlineXML, carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p61/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of P61 is designed to do, as intent. High-energy white-beam / energy-dispersive diffraction reuses the pending `energy_dispersive_diffraction` Method (`TECH-1`).

## Governance

[Governance](governance.md): who will act at P61 and the trust shape that gates their commands. People and agents are facility principals at the [PETRA III Site](../petra-iii/index.md).

## Model

[Model](model.md): the developer's by-kind index, P61's place as the final OnlineXML-modelled PETRA III beamline, and the record of what is deliberately deferred.

## Not yet documented

P61 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals are not in the OnlineXML and are not invented here (`PSS-1`).
