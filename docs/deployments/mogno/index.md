# MOGNO

*The Sirius X-ray micro and nanotomography beamline, and CORA's first deployment at a South American facility. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `MOGNO` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [Sirius](../sirius/index.md) (bound via `facility_code = "sirius"`, `FacilityKind = Site`) |
| Status | First cut, reverse-engineered from papers, design-phase (two tomography stations; scenarios deferred) |
| Source | A 3.2 T dipole / superbend, quasi-monochromatic cone beam at three working energies |
| Control stack | EPICS IOCs + a TATU FPGA trigger (the floor), driven by the beamline's custom PyEpics application stack (`mgn-devices` / `mgn-routines` / `mgn-control-guis`), carried confirm (`CTRL-1`) |

!!! warning "First cut, from papers, confirm-pending by intent"
    This scaffold was reverse-engineered from two published papers (Campoi et al. 2025, the MOGNO software architecture; Archilha et al. 2022, the beamline) and the public [Sirius MOGNO facility page](https://lnls.cnpem.br/facilities/mogno/). Unlike the NSLS-II and Diamond scaffolds, MOGNO has no public controls configuration, so there are no EPICS PVs to read: every device binds a catalog Family but carries no handle and no vendor Model. Every value is carried `confirm` until MOGNO staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes MOGNO different

MOGNO is two firsts at once. It is **CORA's eighth Site** (Sirius, the Brazilian Synchrotron Light Laboratory at CNPEM, Campinas) and the fleet's **first South American facility**. Its science is cone-beam X-ray tomography across two endstations: a nanotomography station reaching ~120 nm with a set of elliptical focusing mirrors, and a microtomography station with a field of view to tens of millimetres, both fed by a quasi-monochromatic dipole source at three working energies (21.5 / 39 / 67.7 keV).

For the modelling, MOGNO's significance is twofold:

- **It is a reuse-and-reinforce tomography deployment.** MOGNO coins no new Family and no new Method: it binds the existing tomography families (`RotaryStage`, `LinearStage`, `Camera`, `Scintillator`, `Mirror`, `Slit`, `TimingController`, `PseudoAxis`) and reuses the graduated `tomography` Method, the way the APS 2-BM pilot and NSLS-II FXI do. It is the tomography spine landing on a third facility.
- **It is the fleet's first custom-Python application layer.** MOGNO's orchestration is neither Bluesky (the 2-BM / FXI / NSLS-II house style) nor BLISS (ESRF) nor Sardana (MAX IV): it is a beamline-owned PyEpics stack. That makes the orchestration seam unusually clean to state, and is the reason MOGNO is a useful test that the seam model does not secretly assume Bluesky.

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| The shared source and optics | Yes | The dipole source, the elliptical focusing mirrors, the beam-defining slits |
| The nanotomography station | Yes | The rotation axis and the fine three-axis sample positioner at the nanofocus |
| The microtomography station | Yes | The large-field-of-view rotation axis and sample positioner |
| The detector chain | Yes | The high-Z photon-counting detector, the indirect scintillator + sCMOS chain, the cone-beam magnification axis |
| The control seam | Named | EPICS + TATU floor, the custom `mgn-*` orchestration above it; handles pending (`CTRL-1`) |
| Exact device handles and models | No | No public controls config exists; PVs, controller boxes, and vendor models are carried confirm-pending |
| Reconstruction (`ssc-raft` on HPC) | Named, not built | The compute axis is named on [Model](model.md); not modelled as Assets |
| PSS permit signals | No | Absent from public sources, carried pending, not invented (`PSS-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A new Site, the first in South America.** Sirius is the 8th Site (`deployments/sirius/site.yaml`); its full operating beamline catalog is listed for context, but only MOGNO is modelled.
- **No new family, no new method.** Every device binds an existing tomography Family; the `tomography` Method is reused. The catalog is unchanged.
- **The TATU trigger binds `TimingController`.** The FPGA trigger/timer that hardware-syncs projection acquisition is the 2-BM softGlueZynq / FXI Zebra precedent.
- **Cone-beam magnification is a `PseudoAxis`.** The sample-along-the-cone "zoom" is a virtual axis over the sample and detector distances, the FXI Magnification precedent.

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the dipole source and ring state, the elliptical focusing mirrors, and the beam-defining slits.
- [Nanotomography](equipment/nanotomography.md): the nanofocus rotation axis and the fine three-axis sample positioner.
- [Microtomography](equipment/microtomography.md): the large-field-of-view rotation axis and sample positioner.
- [Detector](equipment/detector.md): the high-Z photon-counting detector, the indirect scintillator + sCMOS chain, and the cone-beam magnification axis.

Cutting across them:

- [Controls](equipment/controls.md): the EPICS + TATU control floor and the custom `mgn-*` orchestration seam; handles carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/mogno/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of MOGNO is designed to do, as intent. Tomography is already in CORA's catalog, so the Method renders linked, carried pending until the technique enters scope (`TECH-1`).

## Governance

[Governance](governance.md): who will act at MOGNO and the trust shape that gates their commands. People and agents are facility principals at the [Sirius Site](../sirius/index.md).

## Model

[Model](model.md): the developer's by-kind index, the new Sirius Site, the reuse-and-reinforce posture, the compute axis named for reconstruction, and the record of what is deliberately deferred.

## Not yet documented

MOGNO is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals and shutters are absent from public sources and are not invented here (`PSS-1`).
