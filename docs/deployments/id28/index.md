# ID28

*The ESRF beamline for momentum-resolved inelastic X-ray scattering (IXS), and CORA's second ESRF deployment. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `ID28` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [ESRF](../esrf/index.md) (bound via `facility_code = "esrf"`, `FacilityKind = Site`) |
| Sector | `ID28` (an undulator IXS beamline; PV space on the ESRF BLISS Beacon) |
| Status | First cut, reverse-engineered, design-phase (the optics + the eh1 spectrometer endstation; scenarios deferred) |
| Source | Two in-vacuum undulators (IVU22a, IVU13-3c) on the ESRF_Undulator device server |
| Control stack | ESRF BLISS / Beacon over Tango + IcePAP (the ID32 house-style); handles read from the public Beacon config, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from the ESRF's open BLISS Beacon device database ([gitlab.esrf.fr/id28/beamline_configuration](https://gitlab.esrf.fr/id28/beamline_configuration), a git mirror of the live config). The BLISS / Tango / IcePAP handles are real and read from the config; vendor part numbers, serials, energy ranges, and physical positions are not in it and are open questions. Every value is carried as `confirm` until ID28 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes ID28 different

ID28 is CORA's second ESRF beamline (after ID32), and it deepens the fleet's inelastic-scattering coverage with a distinct flavor: **momentum-resolved hard X-ray inelastic scattering (IXS)**. A high-resolution backscattering monochromator sets a meV-resolution incident energy, scanned by tuning the crystal temperature rather than a Bragg angle; the sample scatters; and a multi-analyzer crystal spectrometer on a two-theta arm energy-analyzes the scattered beam in backscattering, mapping phonon and collective-excitation dispersions across momentum transfer. The fleet has soft RIXS (SIX, ID32) and the NSLS-II IXS beamline; ID28 is the ESRF hard X-ray IXS instrument.

For the modelling, ID28 adds a **further `SpectrometerArm` consumer**: its multi-analyzer arm binds the family SIX coined and ID32 brought to a rule-of-three. That sighting reinforced the graduation (`RIXS-1`), which has since landed as a catalog Family; ID28's arm binds it like any catalog Family, coining no new family of its own.

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics (`id28-optics`) | Yes | The two in-vacuum undulators, the high-resolution backscattering monochromator, the incident-energy pseudo-axis (over the F700 crystal-temperature controller), the HFM / VFM focusing mirrors, the primary / mono slits, the oh2 beam-position monitor, the front-end shutter |
| IXS endstation (`id28-eh1`) | Yes | The multi-analyzer spectrometer arm (catalog `SpectrometerArm`), the scattering-geometry sample stage, the sample slits, the sample-temperature cryostats, the detectors |
| The SpectrometerArm graduation | Landed | A further consumer after SIX + ID32; the graduation has landed as a catalog Family (`RIXS-1`) |
| The analyzer-crystal array identity | Named, not built | The inclined analyzer crystals are a per-Asset setting; promoting them to child Assets is the nested-component question (`IXS-1`) |
| Exact sample-stage / per-analyzer-detector handles | No | Carried confirm-pending (`SAMPLE-1`, `DET-1`); the arm, mono, mirrors, and cryostats carry real BLISS handles |
| PSS permit signals and vacuum extent | No | The shutters are modelled (front-end + `bsh*`); the permit leaves behind them and the vacuum extent are absent from the config, carried pending, not invented (`PSS-1`, `SUP-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A second ESRF beamline on the BLISS control plane.** ID28 re-tests the ESRF Site kernel and the Tango / IcePAP house-style established at ID32; handles are opaque edge strings over the `ControlPort` (`CTRL-1`).
- **The multi-analyzer arm binds the catalog `SpectrometerArm` (graduated, `RIXS-1`).** A further consumer after SIX + ID32; that sighting reinforced the graduation, which has since landed. The analyzer-crystal array (a2 / a3 / a4) is a per-Asset setting, not a new family (`IXS-1`).
- **IXS reuses the pending `inelastic_x_ray_scattering` Method.** The second consumer after the NSLS-II IXS beamline; no new slug (`TECH-1`).
- **The incident energy is temperature-scanned, not angle-scanned.** The backscattering crystal's energy is tuned via the ASL F700 temperature controller (`monot` / `deltae`); CORA realizes the `BeamEnergy` `PseudoAxis` over it, decoupled from the `Monochromator` orientation (`MONO-1`).
- **No new family, nothing graduates here.** The backscattering mono binds `Monochromator`, the benders `Mirror`, the slits `Slit`, the detectors `Camera`, the cryostats `TemperatureController`, the front-end shutter `Shutter`; the catalog is unchanged.

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the storage-ring state and front-end shutter, the two in-vacuum undulators, the backscattering monochromator, the incident-energy pseudo-axis, the focusing mirrors, the beam-defining slits, and the beam-position monitor.
- [Sample](equipment/sample.md): the IXS scattering-geometry sample stage, the sample slits, and the sample-temperature cryostats.
- [Detector](equipment/detector.md): the multi-analyzer spectrometer arm and the counting detectors.

Cutting across them:

- [Controls](equipment/controls.md): the BLISS / Tango / IcePAP control stack and the BLISS-orchestration seam; handles bound from the public Beacon config and carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/id28/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of ID28 is designed to do, as intent. Momentum-resolved IXS reuses the pending `inelastic_x_ray_scattering` Method and renders unlinked, carried pending (`TECH-1`).

## Governance

[Governance](governance.md): who will act at ID28 and the trust shape that gates their commands. People and agents are facility principals at the [ESRF Site](../esrf/index.md).

## Model

[Model](model.md): the developer's by-kind index, the further SpectrometerArm consumer, and the record of what is deliberately deferred.

## Not yet documented

ID28 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The shutters are in the BLISS config and are modelled; the PSS permit signals behind them are not, and are not invented here (`PSS-1`).
