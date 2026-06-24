# FXI

*Full-field X-ray imaging and tomography at NSLS-II, beamline 18-ID. This page walks the beamline and how a measurement gets done on it. The model is reverse-engineered from public configuration, not yet confirmed by FXI staff.*

| Property | Value |
| --- | --- |
| Asset | `FXI` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 18` (organizational grouping; PV namespace `XF:18ID*`) |
| Institution | Brookhaven National Laboratory (context; not modeled as an Asset or Facility) |
| Status | Design projection from public config (operational beamline; CORA not connected) |
| Floor control system | EPICS (the beamline's; CORA actuates through it) |

!!! note "How CORA would land on FXI"
    These pages describe how CORA would model, govern, conduct, and record FXI if it were deployed there. They are not a survey of the beamline's current software. The hardware facts (devices, EPICS PVs, axes, enclosures, quirks) are read from public NSLS-II open source (the [`NSLS2/fxi-profile-collection`](https://github.com/NSLS2/fxi-profile-collection) profile collection) and verified against it; vendor part numbers, controller boxes, and physical positions are not in it, so they, and every read value, are carried `confirm` until FXI staff verify them ([Open questions](questions.md)). What CORA would bring (its Conductor, its data of record, its governance) is CORA's own design landing on the beamline's hardware, not the beamline's existing stack restated.

## The beamline

The systems the beam passes through, in three stages, plus the controls that drive them and the resources they draw on. See [the beamline overview](equipment/index.md) for how the areas relate.

Along the beam, in order:

- [Source](beamline.md): the insertion-device source and the optics that condition the beam and set its energy (double-crystal monochromator, two mirrors, white-beam slit, attenuating filters, flux diagnostics), rendered as the generated source-stage device walk.
- [Sample](equipment/sample.md): the TXM sample stage and the transmission-microscopy optics around it (condenser, aperture, zone plate, phase ring, Bertrand lens).
- [Detector](equipment/detector.md): the imaging detector, a scintillator-relay-camera system, with the magnification computed from the zone-plate and detector positions.

Cutting across all three:

- [Controls](equipment/controls.md): the Zebra position-capture trigger box and the motion controllers, related to the hardware by `controller_id`.
- Resources: the continuously-available supplies a run needs (beam, cooling, vacuum, liquid nitrogen), tracked under [Operations > Supplies](operations.md#supplies).

The cross-cutting reference view is the [Inventory](inventory.md): the flat Asset tree by `parent_id` with families, PVs, and the values still pending confirmation. The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/fxi/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what FXI can do, each a portable [Catalog](../../catalog/methods.md) Method bound through an NSLS-II [Practice](../nsls2/index.md#the-techniques-adapted-here). The function view survives equipment swaps.

## Operations

[Operations](operations.md) is the runbook for getting ready and measuring. It ties together [Procedures](procedures.md) (alignment, calibration, recovery), [Recipes](recipes.md) (deployment-bound step sequences that expand into Procedures), [Enclosures](enclosures.md) (the optics hutch `18-IDA` and experiment hutch `18-IDB`), and [Cautions](cautions.md). These pages are derived from the public scan plans, not from operating the beamline, so they carry the same `confirm` posture.

## Experiment

[Experiment](experiment.md): the per-experiment view CORA's model would record, the subjects, runs, campaigns, datasets, and decisions of a beamtime. Described here as shape; CORA is not running FXI, so there are no live instances.

## Governance

[Governance](governance.md): who may act at FXI and the trust shape CORA applies to their commands. People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here); CORA brings its own per-Actor authority. The human roster is not yet known.

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's FXI content lives.
