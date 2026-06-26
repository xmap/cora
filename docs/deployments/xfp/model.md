# Model

*The developer's index into where XFP content lives, why this dose-delivery beamline coins no new family, how it models a beamline with no detector and an offline readout, and the record of what is deliberately deferred. First cut.*

XFP is a descriptor-and-docs scaffold today, reverse-engineered from the beamline's profile collection: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/xfp/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/xfp/beamline.yaml) | the device walk with bound PVs; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/nsls2/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/nsls2/site.yaml) | the NSLS-II facility surface; `XFP` added to its beamline list, with the footprinting Practices |
| Extraction provenance | [NSLS2/xfp-profile-collection](https://github.com/NSLS2/xfp-profile-collection) | the `startup/` device definitions the descriptor was curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; every device reuses an existing catalog or loose Family (below) |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; `x_ray_footprinting` is a new pending slug, the fleet's first dose-delivery Method (`TECH-1`) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers XFP Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes XFP new

XFP is the most structurally distinct deployment in the fleet. Every other beamline CORA models is a measurement beamline: condition a beam, place a sample, record a detector signal. XFP is a **dose-delivery** beamline with **no detector**. Its contributions:

- **Dose as the experiment variable.** The controlled quantity is the delivered radiolytic dose (exposure time times incident flux times attenuation), not a detector setting. The whole apparatus, the timed shutters, the delay-generator-fired millisecond fast shutter, the Al filter wheel, and the flux monitors, exists to set and measure that dose.
- **A sample-and-record output, not frames.** A footprinting run produces a footprinted sample (an irradiated aliquot) plus a dose record (exposure time, filter thickness, flux time-series, well / tube identity). There are no measurement frames.
- **The offline-readout seam.** The structural readout (which residues were modified) is offline mass spectrometry, downstream and off the beamline. CORA is the system of record for the dose and the sample provenance; the MS analysis is a separate, later step.
- **A solution Subject.** Like LIX, the specimen is a biological macromolecule in a buffer, delivered fluidically.

## No new families

XFP coins no new Family and changes nothing in the catalog. The whole device tree reuses existing vocabulary; the novelty is in the Method, the Subject, and the seam, not in device classes.

- **17-BM is a bending-magnet, white / pink beam source** (no insertion device, no monochromator in the footprinting path); machine state is observed through the loose `StorageRing`, and the white-versus-mono scope is `SRC-1` / `WHITE-1`.
- **The dose chain reuses the catalog:** the bendable mirror binds `Mirror`; the slits bind `Slit`; the Al filter wheel binds `Filter` (it sets the dose rate); the timed shutters bind `Shutter`; the delay generator that fires the millisecond Uniblitz fast shutter binds `TimingController` (its opening-time setpoint is the dose time); the QuadEM electrometers bind `FluxMonitor`; the Sydor beam-position monitor binds the loose `BeamPositionMonitor` (held under review, `DIAG-1`); the sample stages bind `LinearStage`.

## How a beamline with no detector is modelled

XFP has no Detector-role imaging device, and CORA models that honestly rather than inventing one:

- the detection side holds **flux / dose monitors** (`FluxMonitor`, the loose `BeamPositionMonitor`), which measure the delivered dose, not a sample signal;
- the dose-delivery role is expressed by the **Source gating** (Shutter + `TimingController` + `Filter`) plus those flux monitors, not by a detector;
- the structural readout is the **offline-readout seam**: the run's product is a footprinted sample plus a dose record, and the mass-spec analysis happens downstream, off the beamline (`READOUT-1`).

This is the deliberate inversion: where a measurement beamline's run is anchored on a Dataset of detector frames, an XFP run is anchored on a dose record and a Subject (the footprinted aliquot), with the structural Dataset produced elsewhere and linked back later.

## The FlowController rule-of-three

The one device reuse worth naming is the sample-delivery pump. Its anatomy is a settable flow / pump actuator (rate / volume setpoints, a run command), exactly the existing loose `FlowController` Family that i22, 7-BM, and LIX already use. So the pump **reuses** `FlowController`; it coins nothing. XFP is its **fourth** consumer (i22, 7-BM, LIX, XFP), past the rule-of-three that LIX already fired, so the graduation is now overdue. As with LIX, the `_PROMOTION_REVIEWED` note for `FlowController` is updated (to n=4) and the graduation itself, a YAML-and-docs change presenting the existing `Regulator` Role, like `TemperatureController` and `FluxMonitor`, re-pointing i22 / 7-BM / LIX / XFP, stays a separate gated decision, not folded into this scaffold (`FLOW-1`, `FLUID-1`).

## Deliberately not here yet

- **The fraction collector Family (`FC-1`).** The fraction collector is a PV-bound aliquot-routing actuator with no clean existing Family. At n=1 CORA does not coin a `FractionCollector` Family; it is carried in the sample-custody seam (the footprinted-sample hand-off to offline MS).
- **The 96-well plate handler (`HT-1`).** The plate is addressed in pure Python (8 columns x 12 rows, a coordinate table, no robot and no PV); it is a Procedure over the spine plus a Subject custody thread, the i03 / MX3 / LIX custody-as-Procedure precedent (XFP at the no-robot end of that spectrum), not a device Family.
- **The offline mass-spec readout (`READOUT-1`).** The structural analysis is downstream, off the beamline, and absent from the profile collection. A future integration could link the offline MS result back to the dose record; it is not modelled here.
- **The Method.** Whether `x_ray_footprinting` (or a broader controlled-dose / irradiation Capability) enters CORA's catalog is an owner decision; the Practices render unlinked, pending (`TECH-1`).
- **The intermittently-connected and out-of-scope hardware.** The 0-9 mm Al z-attenuator, the beam-defining pinhole stages, the greenfield Galil stages, and the temperature / bias diagnostics are intermittently connected or read-only and not modelled as core devices (`ATTN-1`, `TEMP-1`); the monochromatic XAS endstation (ES:3) is a separate endstation, out of scope for footprinting (`WHITE-1`).
- **The time-resolved mixing mode.** The stopped-flow time-resolved footprinting mode is flagged unfinished in the source; no Practice is recorded for it (`TECH-1`).
- **The simulated devices and full asset-tree scenarios.** No `test_xfp_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
