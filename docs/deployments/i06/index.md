# I06

*The nanoscience soft X-ray beamline at Diamond Light Source, and CORA's first variable-polarization (APPLE-II) source and first PEEM endstation. This page walks the shared spine and both endstations CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `I06` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [Diamond Light Source](../diamond/index.md) (bound via `facility_code = "diamond"`, `FacilityKind = Site`) |
| Sector | `Sector 06` (PV zones `BL06I` / `SR06I` / `BL06J` / `BL06K`; not a registered Asset) |
| Status | First cut, reverse-engineered, design-phase (shared spine plus both endstations; the PEEM image detector and the i06-1 diffraction detector deferred) |
| Source | Twin APPLE-II undulators, the downstream IDD (gap `SR06I-MO-SERVC-01`) and the upstream IDU (gap `SR06I-MO-SERVC-21`), driving incident energy and polarization (`SRC-1`, `POL-2`) |
| Control stack | Diamond EPICS / ophyd-async (the same floor as I22, I03, I15-1, I11, I24); handles read from dodal, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) controls library (the `i06.py`, `i06_shared.py`, `i06_1.py`, and `i06_2.py` beamline factories and the `src/dodal/devices/` classes). EPICS PVs are real and read from dodal; vendor part numbers, serials, and physical positions are not in dodal and are open questions. Every value is carried as `confirm` until I06 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes I06 different

I06 carries two firsts for the fleet, and both are absorbed by reuse rather than by new vocabulary.

- **The first APPLE-II source, so the first beamline that drives polarization as an experiment axis.** An APPLE-II undulator sets the incident X-ray polarization, not just the energy. I06 is the first beamline whose source can vary it, so it is the first to carry POLARIZATION as a first-class experiment axis (`POL-1`) alongside the incident-energy axis: linear horizontal (LH), linear vertical (LV), arbitrary-angle linear (LA), circular positive (PC) and negative (NC), plus third-harmonic variants (`POL-2`). That is exactly what magnetic dichroism (XMCD / XMLD) needs. The APPLE-II coins no new Family: it is the same source-undulator anatomy as the EPUs at SIX / CSX / ESM, so it binds the catalog `InsertionDevice`. The polarization axis coins no new Family either: it is a sibling of the incident-energy pseudo-axis and binds the catalog `PseudoAxis`.
- **The first PEEM endstation.** Photoemission electron microscopy is an electron-IMAGING technique, distinct from the electron-energy analysis of ARPES at ESM / SST. The PEEM sample manipulators reuse the catalog `Manipulator` graduated by SIX and ESM. The PEEM electron-optical column and its magnified electron-image detector are absent from dodal and are deferred, not coined (`PEEM-1`): that anatomy is an `ElectronMicroscope`, distinct from the photon `Camera` and from the energy-analyzing catalog `ElectronAnalyzer`, and it is not coined here.

The net: I06 introduces a genuinely-new modelling PRIMITIVE, an experiment-driven polarization axis, and expresses it entirely through existing Families. The catalog is unchanged and nothing graduates.

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics spine (`BL06I` / `SR06I`) | Yes | The twin APPLE-II undulators, the plane-grating monochromator, the incident-energy and polarization pseudo-axes, and the i06-branch PEEM stage |
| i06-1 diffraction-dichroism endstation (`BL06J`) | Yes | The diffractometer arm, the reciprocal-space pseudo-axis, the absorption stage, and the two Lakeshore 336 temperature controllers |
| i06-2 PEEM endstation (`BL06K`) | Yes | The UHV PEEM sample manipulator (`PEEM-1` defers only the imaging column) |
| The PEEM electron-optical column and image detector | No | Absent from dodal; the loose `ElectronMicroscope` anatomy, deferred not coined (`PEEM-1`) |
| The i06-1 diffraction scattering detector and flux / drain-current monitor | No | Absent from dodal; deferred not invented (`DET-1`) |
| PSS permit signals and the photon / front-end shutters | No | Absent from dodal; carried pending, not invented (`PSS-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **APPLE-II binds the catalog `InsertionDevice` (reuse).** An APPLE-II is the same source-undulator anatomy as the EPUs at SIX / CSX / ESM. The polarization phase rows, the energy-to-gap polynomial, and the controller are per-Asset settings on the bound Model, which resolves `SRC-1` toward reuse rather than a coin.
- **POLARIZATION binds the catalog `PseudoAxis` (reuse).** The polarization axis is a sibling of the incident-energy pseudo-axis, on the 2-BM beam-energy precedent. The polarization value set (LH / LV / PC / NC / LA plus third-harmonic variants) is the axis domain; the controller's polarization-to-phase conversion is its partition rule, carried rule-less because the live I06 controller owns the conversion (`POL-1`, `POL-2`). This is the genuinely-new modelling primitive expressed by reuse.
- **The PEEM column and detector are deferred (`PEEM-1`), not coined.** No PV in dodal covers the electron-optical column or its magnified electron-image detector, so the `ElectronMicroscope` anatomy is named and deferred. The PEEM sample manipulators bind the catalog `Manipulator` (reuse).
- **The i06-1 diffraction detector and flux monitor are deferred (`DET-1`).** Both are absent from dodal, so the first cut models the diffractometer arm and its reciprocal-space pseudo-axis but not the scattering detector or electron-yield monitor.

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the machine-level storage-ring state, the twin APPLE-II undulators driving the incident-energy and polarization handles, and the soft X-ray plane-grating monochromator (gratings 150 / 400 / 1200 l/mm, 70 to 2200 eV).
- [Sample](equipment/sample.md): the i06-1 diffractometer and its sample circles, the absorption stage, and the two Lakeshore 336 temperature controllers, plus the i06-2 and i06-branch PEEM sample manipulators.
- [Detector](equipment/detector.md): the detector arm of the i06-1 diffractometer; the i06-1 scattering detector and flux monitor (`DET-1`) and the PEEM electron-image detector (`PEEM-1`) are absent from dodal and deferred.

Cutting across them:

- [Controls](equipment/controls.md): the Diamond EPICS / ophyd-async control stack and the bluesky-orchestration seam CORA conducts over where it replaces it; handles read from dodal and carried confirm (`CTRL-1`).

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i06/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of I06 is designed to do, as intent. XMCD shares the 4-ID `xmcd` Method; XMLD, PEEM, and resonant soft X-ray diffraction render as pending slugs (`xmld`, `photoemission_microscopy` with the imaging detector deferred `PEEM-1`, and the shared `resonant_scattering` Method). All carry pending Site Practices at the [Diamond Site](../diamond/index.md#the-techniques-adapted-here).

## Governance

[Governance](governance.md): who would act at I06 and the trust shape (Zone plus Conduit plus Policy) that gates their commands. People and autonomous agents are facility principals at the [Diamond Site](../diamond/index.md#who-acts-here), carried pending site-level (`GOV-1`), following the 2-BM governance shape. The PSS search-and-secure permit signals and the photon / front-end shutters are absent from dodal and carried pending, not invented (`PSS-1`); the hazard envelope is a soft X-ray UHV beamline with intense polarized beam and in-situ temperature environments (see [the safety envelope](../diamond/index.md#the-safety-envelope)).

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's I06 content lives, why this first APPLE-II and PEEM deployment coins no new vocabulary, and the record of what is deliberately deferred.

## Not yet documented

I06 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS search-and-secure permit signals and shutters are absent from dodal and not invented here (`PSS-1`); the i06-1 diffraction detector (`DET-1`) and the PEEM electron-image detector and column (`PEEM-1`) are likewise absent and deferred.
