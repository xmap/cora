# ID32

*The ESRF soft X-ray beamline for resonant inelastic X-ray scattering (RIXS) and X-ray magnetic dichroism (XMCD), and CORA's first ESRF deployment. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `ID32` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [ESRF](../esrf/index.md) (bound via `facility_code = "esrf"`, `FacilityKind = Site`) |
| Sector | `ID32` (a soft X-ray APPLE-II beamline; PV space on the ESRF BLISS Beacon, not a registered Asset) |
| Status | First cut, reverse-engineered, design-phase (the shared optics + the RIXS and XMCD endstations; scenarios deferred) |
| Source | Twin APPLE-II undulators on the `id/master/id32` device server |
| Control stack | ESRF BLISS / Beacon over Tango + IcePAP (the fleet's first non-EPICS, non-Sardana house-style); handles read from the public Beacon config, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from the ESRF's open BLISS Beacon device database ([gitlab.esrf.fr/id32/beamline_configuration](https://gitlab.esrf.fr/id32/beamline_configuration), a git mirror of the live `/users/blissadm/local/beamline_configuration`). The Tango / IcePAP / BLISS handles are real and read from the config; vendor part numbers, serials, energy ranges, and physical positions are not in it and are open questions. Every value is carried as `confirm` until ID32 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes ID32 different

ID32 is two firsts at once. It is **CORA's seventh Site** (the ESRF, Grenoble), the largest single-deployment re-test of the Site and Federation kernel, and the **first BLISS / Beacon / Tango / IcePAP control plane** CORA models (the rest are EPICS, or Tango / Sardana at MAX IV). Its science is soft X-ray RIXS on a roughly 5 m dispersive spectrometer arm, plus XMCD and X-ray emission spectroscopy (XES) at a 9 Tesla high-field-magnet endstation, both fed by twin APPLE-II undulators through a soft X-ray plane-grating monochromator.

For the modelling, ID32's significance is that it brings **three loose families to a genuine rule-of-three** at once:

- **`SpectrometerArm`** reached the rule-of-three: ID32 carries the same `SpectrometerArmsController` class instantiated twice (the RIXS arm and the XES arm), so with the SIX soft-RIXS arm the family was sighted three times. It has since **graduated** into the catalog (earned across SIX + ID32 RIXS/XES + ID28).
- **`Magnet`** gets a third consumer (4-ID + i10-1 + the ID32 9 T XMCD magnet).
- **`PolarizationAnalyzer`** gets a further consumer (4-ID + i10 + the ID32 RIXS polarimeter); it has since graduated to a catalog Family across 4-ID / i10 / ID32 / P09, presenting Positioner.

Per the owner decision, each graduation is a dedicated gated catalog PR (see [Model](model.md#loose-families-held-at-the-rule-of-three)). `SpectrometerArm`, `Magnet`, and `PolarizationAnalyzer` have all graduated. ID32 coins no new Family.

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Shared optics (`id32-optics`) | Yes | The twin APPLE-II undulators, the polarization and incident-energy pseudo-axes, the soft X-ray PGM, the focusing mirrors, the beam slits |
| RIXS endstation (`id32-rixs`) | Yes | The dispersive RIXS spectrometer arm (catalog `SpectrometerArm`), the 4-circle diffractometer + reciprocal-space axis, the scattered-beam polarimeter (catalog `PolarizationAnalyzer`), the Andor CCD |
| XMCD endstation (`id32-xmcd`) | Yes | The 9 T XMCD magnet (catalog `Magnet`), the LakeShore VTI and coil-diagnostic controllers, the XES spectrometer arm (catalog `SpectrometerArm`), the Andor CCD, the sample stage |
| The loose-family graduations | Done | `SpectrometerArm` (`RIXS-1`), `Magnet` (`MAG-1`), and `PolarizationAnalyzer` (across 4-ID / i10 / ID32 / P09, presenting Positioner, `POL-2`) all graduated, each via its own gated catalog PR |
| Exact optics handles | No | The PGM, mirrors, slits, diffractometer axes, and XMCD sample stage are carried confirm-pending (`MONO-1`, `OPT-1`, `OPT-2`, `DIFF-1`, `SAMPLE-1`) |
| PSS permit signals and vacuum extent | No | Absent from the BLISS config, carried pending, not invented (`PSS-1`, `SUP-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A new Site and a new control house-style.** ESRF is the 7th Site (`deployments/esrf/site.yaml`); the BLISS / Tango / IcePAP handles are modelled as opaque edge strings over the `ControlPort`, the way the MX3 heterogeneous-control precedent does (`CTRL-1`).
- **The polarization spine reuses i06 / i10.** The twin APPLE-II undulators bind `InsertionDevice` and the polarization is a `PseudoAxis` over the undulator phase (`POL-1`).
- **Three loose families reached the rule-of-three and graduated.** `SpectrometerArm` (RIXS + XES arms, the same controller class) and `Magnet` (the 9 T XMCD magnet) have since graduated into the catalog; `PolarizationAnalyzer` (the RIXS polarimeter) has also graduated to a catalog Family across 4-ID / i10 / ID32 / P09, presenting Positioner (`POL-2`). Each graduation landed via its own dedicated PR.
- **No new family coined here.** The PGM binds `GratingMonochromator`, the diffractometer `Goniometer`, the CCDs `Camera`, the LakeShores `TemperatureController`; the dispersive arms bind the graduated `SpectrometerArm`, the 9 T magnet the graduated `Magnet`, and the polarimeter the graduated `PolarizationAnalyzer`.

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the storage-ring state, the twin APPLE-II undulators, the polarization and incident-energy pseudo-axes, the PGM, the focusing mirrors, and the beam slits.
- [Sample](equipment/sample.md): the RIXS 4-circle diffractometer, the XMCD 9 T magnet and its VTI temperature control, and the XMCD sample stage.
- [Detector](equipment/detector.md): the RIXS and XES dispersive spectrometer arms, the scattered-beam polarimeter, and the two Andor CCDs.

Cutting across them:

- [Controls](equipment/controls.md): the BLISS / Tango / IcePAP control stack and the BLISS-orchestration seam; handles bound from the public Beacon config and carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/id32/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of ID32 is designed to do, as intent. RIXS, XMCD, and XES are new to CORA's catalog and render unlinked, carried pending (`TECH-1`).

## Governance

[Governance](governance.md): who will act at ID32 and the trust shape that gates their commands. People and agents are facility principals at the [ESRF Site](../esrf/index.md).

## Model

[Model](model.md): the developer's by-kind index, the new Site and control house-style, the three loose families held at the rule-of-three, and the record of what is deliberately deferred.

## Not yet documented

ID32 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals and shutters are absent from the BLISS config and are not invented here (`PSS-1`).
