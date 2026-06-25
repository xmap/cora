# I10

*The BLADE soft X-ray beamline at Diamond Light Source, the fleet's second variable-polarization (APPLE-II) source and i06's soft X-ray twin. This page walks the shared spine and both endstations CORA models today: RASOR resonant scattering and reflectivity, and the i10-1 / I10J magnet endstation for magnetic dichroism. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `I10` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [Diamond Light Source](../diamond/index.md) (bound via `facility_code = "diamond"`, `FacilityKind = Site`) |
| Sector | `Sector 10` (PV zones `BL10I` / `SR10I` / `ME01D` / `BL10J`; not a registered Asset) |
| Status | First cut, reverse-engineered, design-phase (shared spine plus both endstations; the RASOR and i10-1 point detectors, the upstream diagnostics, and PSS deferred) |
| Source | Twin APPLE-II undulators, the downstream IDD (servo `SR10I-MO-SERVC-01`) and the upstream IDU (servo `SR10I-MO-SERVC-21`), driving incident energy and polarization (`SRC-1`, `POL-1`) |
| Control stack | Diamond EPICS / ophyd-async (the same floor as I22, I03, I15-1, I11, I24, I06); handles read from dodal, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) controls library (the `i10.py`, `i10_shared.py`, and `i10_1.py` beamline factories and the `src/dodal/devices/` classes). EPICS PVs are real and read from dodal; vendor part numbers, serials, and physical positions are not in dodal and are open questions. Every value is carried as `confirm` until I10 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes I10 different

I10 is the fleet's second APPLE-II source after I06, and it is I06's soft X-ray twin: the same twin-APPLE-II plus plane-grating-monochromator spine, here feeding the RASOR and i10-1 branch endstations. The novelty is not a new source primitive but what happens to two families that have now been sighted twice.

- **The polarization axis is reused, not re-coined.** I06 established that an APPLE-II drives incident X-ray polarization as a first-class experiment axis, expressed entirely through existing Families. I10 inherits that precedent directly: the twin APPLE-II binds the catalog `InsertionDevice` and the polarization handle binds the catalog `PseudoAxis`, with the same value domain (LH / LV / PC / NC / LA plus third-harmonic variants). The continuous linear-arbitrary-angle is the continuous realization of the LA value WITHIN that same polarization axis, not a second axis and not a new family (`POL-1`).
- **Two loose families reach a SECOND sighting, and I10 holds them.** RASOR's motorized polarization-analysis arm binds the loose `PolarizationAnalyzer` family, first seen at 4-ID; this is its second sighting (`POL-2`). The i10-1 magnet devices bind the loose `Magnet` family, also first seen at 4-ID; this is its second sighting (`MAG-1`). A second sighting is not the rule-of-three, so both stay HELD under review rather than graduating. The hold-versus-graduate call stays human, and I10 records HOLD.

The net: I10 coins no new Family, nothing graduates, and the catalog is unchanged. The deployment's contribution is the second data point on two loose families and the reuse of the polarization axis on a twin source.

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics spine (`BL10I` / `SR10I`) | Yes | The twin APPLE-II undulators, the plane-grating monochromator, the collimating / switching / focusing mirrors, the optics slits, and the incident-energy and polarization pseudo-axes |
| RASOR endstation (`ME01D`) | Yes | The diffractometer arm and reciprocal-space pseudo-axis, the loose `PolarizationAnalyzer` arm (`POL-2`), the cryostat sample stage, the pinhole, and the Lakeshore 340 temperature controller |
| i10-1 / I10J magnet endstation (`BL10J`) | Yes | The loose `Magnet` family (electromagnet plus the superconducting field-sweep magnet, `MAG-1`), the magnet stages, the focusing mirror and slits, and the Lakeshore 336 temperature controller |
| The RASOR and i10-1 point / current-integrating detectors | No | Modelled as `FluxMonitor` where bound; no area detector exists, deferred not invented (`DET-1`) |
| The upstream diagnostics | No | Carried pending, not invented (`SUP-1`) |
| PSS permit signals and the photon / front-end shutters | No | Absent from dodal; carried pending, not invented (`PSS-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **APPLE-II binds the catalog `InsertionDevice`, polarization binds the catalog `PseudoAxis` (reuse, the merged I06 precedent).** The polarization phase rows, the energy-to-gap polynomial, and the controller are per-Asset settings on the bound Model (`SRC-1`). The polarization value set (LH / LV / PC / NC / LA plus third-harmonic variants) is the axis domain; the continuous linear-arbitrary-angle is the continuous realization of the LA value within that same axis, not a new axis or family, and the live controller owns the conversion rule-less (`POL-1`).
- **The PaStage / POLAN arm binds the loose `PolarizationAnalyzer` family, HELD under review (`POL-2`).** This is a CORA modelling CHOICE: model RASOR's defining polarization-analysis role on the real motorized arm rather than hide it, even though dodal exposes the arm's motors only and the analyzer crystal is implicit hardware. This is the family's second sighting after 4-ID; the rule-of-three is not met, so I10 records HOLD.
- **Both magnet devices bind the loose `Magnet` family, HELD under review (`MAG-1`).** The set-and-read electromagnet and the superconducting field-sweep magnet are ONE family; the field-sweep is a per-Asset affordance, not a split. This is the family's second sighting after 4-ID; I10 records HOLD.
- **No area detector at either endstation; point and current-integrating detection binds `FluxMonitor` (`DET-1`).** RASOR's scaler-channel point, incident-flux, fluorescence, and drain-current / total-electron-yield channels (through Femto / SR570 current amplifiers) and the i10-1 point channels are the science detectors, so they bind `FluxMonitor`.
- **Zero new families coined, nothing graduates, the catalog is unchanged.**

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the machine-level storage-ring state (observe-only, `MACHINE-1`), the twin APPLE-II undulators driving the incident-energy and polarization handles (`SRC-1`, `ENERGY-1`, `POL-1`), the plane-grating monochromator (`MONO-1`), and the collimating, switching, and focusing mirrors that select the RASOR or i10-1 branch.
- [Sample](equipment/sample.md): the RASOR diffractometer and its sample circles (`DIFF-1`, `DIFF-2`), the loose `PolarizationAnalyzer` arm (`POL-2`), the cryostat sample stage and pinhole (`STAGE-1`), the i10-1 magnets and magnet stages (`MAG-1`), and the Lakeshore 340 and Lakeshore 336 temperature controllers (`TEMP-1`).
- [Detector](equipment/detector.md): the RASOR and i10-1 point detection bound to `FluxMonitor`; no area detector exists at either endstation (`DET-1`).

Cutting across them:

- [Controls](equipment/controls.md): the Diamond EPICS / ophyd-async control stack and the bluesky-orchestration seam CORA conducts over where it replaces it; handles read from dodal and carried confirm (`CTRL-1`).

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i10/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of I10 is designed to do, as intent. Resonant soft X-ray scattering shares the 4-ID `resonant_scattering` Method and XMCD shares the 4-ID `xmcd` Method; soft X-ray reflectivity renders as a new pending slug (`reflectivity`, the R in RASOR) and XMLD shares the I06 `xmld` slug. All four carry pending Site Practices (`I10_resonant_scattering_practice`, `I10_reflectivity_practice`, `I10_xmcd_practice`, `I10_xmld_practice`) at the [Diamond Site](../diamond/index.md#the-techniques-adapted-here) (`TECH-1`).

## Governance

[Governance](governance.md): who would act at I10 and the trust shape (Zone plus Conduit plus Policy) that gates their commands. People and autonomous agents are facility principals at the [Diamond Site](../diamond/index.md#who-acts-here), carried pending site-level (`GOV-1`), following the 2-BM governance shape. The PSS search-and-secure permit signals and the photon / front-end shutters are absent from dodal and carried pending, not invented (`PSS-1`); the hazard envelope is a soft X-ray UHV beamline with an intense polarized beam, high magnetic fields (a superconducting magnet at i10-1), and cryogenics (see [the safety envelope](../diamond/index.md#the-safety-envelope)).

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's I10 content lives, why this second APPLE-II deployment coins no new vocabulary, and the record of what is deliberately deferred, including the two loose families (`PolarizationAnalyzer` `POL-2`, `Magnet` `MAG-1`) held at their second sighting.

## Not yet documented

I10 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS search-and-secure permit signals and shutters are absent from dodal and not invented here (`PSS-1`); the RASOR and i10-1 point detectors are bound to `FluxMonitor` with no area detector to defer (`DET-1`); and the upstream diagnostics are carried pending (`SUP-1`).
