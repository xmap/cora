# IXS

*The momentum-resolved hard X-ray Inelastic X-ray Scattering beamline at NSLS-II, and CORA's first hard inelastic-scattering deployment. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `IXS` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 10` (PV namespace `XF:10ID*`; not a registered Asset) |
| Status | First cut, reverse-engineered, design-phase (descriptor + docs; scenarios deferred) |
| Source | An in-vacuum undulator (IVU22) on the `SR:C10-ID` straight |
| Control stack | NSLS-II EPICS / ophyd (the same floor as FXI / HXN / BMM / SRX / SIX / CHX); handles bound from the profile collection, carried confirm |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/ixs-profile-collection](https://github.com/NSLS2/ixs-profile-collection)). EPICS PVs are real and verified against the `startup/*.py` files; vendor part numbers, serials, and physical positions are not in the profile collection and are open questions. Every value is carried as `confirm` until IXS staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes IXS different

IXS is **CORA's first hard inelastic-scattering beamline**, the first photon-in / photon-out energy-LOSS technique in the fleet. The deployments before it cover elastic scattering (SAXS/WAXS, XPDF, powder, XPCS, MX), XRF microprobe, hard X-ray absorption (BMM), and soft resonant inelastic scattering (SIX), but no hard inelastic scattering. What is new is the acquisition shape: set the momentum transfer Q with a six-circle reciprocal-space pseudo-axis, then scan the incident energy against a fixed crystal analyzer, point-detecting the energy-analyzed scattered beam to build I(Q, energy-loss). meV resolution comes from a high-resolution monochromator plus a temperature-stabilized diced crystal analyzer.

The acquisition has three moving parts:

- **Set Q.** A six-circle scattering arm (tth / th / chi / phi) driven by an H/K/L reciprocal-space pseudo-axis places the detector at the scattering angle that selects the momentum transfer.
- **Scan incident energy.** The Si(111) double-crystal monochromator (DCM) and the high-resolution monochromator (HRM2) step the incident energy in meV steps while the analyzed final energy stays fixed; energy transfer is the difference.
- **Point-detect against a fixed analyzer.** A diced crystal energy analyzer Bragg-reflects the scattered beam to a fixed final energy and focuses the energy-selected photons onto quad electrometers, normalized by an I0 scaler. Detection is point / current-integrating, not an area detector.

Almost every device reuses an existing catalog or loose Family. IXS introduces **one** device class new to the catalog, the crystal energy analyzer, modelled as a loose family at n=1 (nothing graduated):

- **A diced crystal energy analyzer.** The signature instrument is a diced multi-crystal Bragg analyzer (six diced crystals, each with orientation and PID temperature stabilization) that selects a fixed final photon energy of the scattered beam and focuses energy-selected photons onto the point detectors. No catalog Family fits this anatomy, so it binds a loose `EnergyAnalyzer` Family, the `<Quantity>Analyzer` sibling of 4-ID's loose `PolarizationAnalyzer` (see [Model](model.md#new-loose-families)).

Everything else (the undulator, the DCM and HRM2 crystal monochromators, the mirrors, the slits, the transfocator, the six-circle arm, the temperature controller, the electrometers) reuses an existing catalog or loose Family.

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics (`XF:10IDA/B/C`) | Yes | The DCM, HRM2, the transfocator, the mirrors, the slits, the secondary source aperture, the transport table |
| IXS endstation (`XF:10IDD`) | Yes | The KB mirrors, the sample stages, the six-circle spectrometer arm, the crystal analyzer, the counting detectors |
| New device classes | Loose at n=1 | `EnergyAnalyzer`: held loose, nothing graduated (see [Model](model.md#new-loose-families)) |
| The six-circle arm | Catalog `Goniometer` | The 8-ID / 4-ID diffractometer anatomy, not SIX's dispersive `SpectrometerArm` (see [Model](model.md#deliberately-not-here-yet)) |
| The analyzer-plus-arm Assembly | No | Deferred as 8-ID / 4-ID deferred their diffractometer Assemblies (`ANALYZER-1`) |
| The simulated devices and legacy SPEC macros | No | A scaffold provenance, not modelled here |
| Integration scenarios + vendor Models | No | Design-phase; the descriptor and docs come first |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **Reuse over coin.** Every device but the energy analyzer binds an existing catalog or loose Family, and the catalog changes nothing. The crystal energy analyzer is the only class no Family covers, and it stays loose at n=1: a second independent hard crystal-analyzer beamline must earn the abstraction before any catalog change.
- **The six-circle arm binds the catalog `Goniometer`.** The scattering arm driven by the reciprocal-space pseudo-axis is the 8-ID / 4-ID six-circle diffractometer anatomy, not SIX's energy-dispersive `SpectrometerArm` (a different, dispersive instrument). In descriptor mode it binds `Goniometer` directly.
- **The analyzer Assembly is named, not built (`ANALYZER-1`).** Whether the crystal analyzer plus the six-circle arm compose an `Assembly(Diffractometer)`-style Fixture is deferred, exactly as 8-ID and 4-ID deferred materializing theirs. The first cut is a flat loose `EnergyAnalyzer` Asset plus a `Goniometer` arm Asset.

## The beamline

- [Source](beamline.md): the generated device walk: the undulator, the front-end slit and transfocator, the DCM and HRM2 and their slits and beam-position monitors, the transport optics, the KB refocusing mirrors, and the endstation optics.
- [Sample](equipment/sample.md): the sample positioning table and the sample-environment translations.
- [Detector](equipment/detector.md): the six-circle spectrometer arm and its reciprocal-space pseudo-axis, the crystal energy analyzer and its thermal stabilization, and the counting electrometers and I0 scaler.

Cutting across them:

- [Controls](equipment/controls.md): the EPICS / ophyd control stack and the bluesky-orchestration seam; handles bound from the profile collection and carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/ixs/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of IXS is designed to do, as intent. Momentum-resolved hard X-ray inelastic scattering is new to CORA's catalog and renders unlinked, carried pending (`TECH-1`).

## Governance

[Governance](governance.md): who will act at IXS and the trust shape that gates their commands. People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md).

## Model

[Model](model.md): the developer's by-kind index, the new loose family this deployment introduces, and the record of what is deliberately deferred.

## Not yet documented

IXS is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS search-and-secure permit signals and shutters are absent from the profile collection and are not invented here (`PSS-1`).
