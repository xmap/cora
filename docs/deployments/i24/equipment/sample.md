# Sample

*The i24 serial endstation. Design-phase; values are reverse-engineered from dodal or inferred.*

The sample stage is the experiment hutch: the vertical goniometer for pin-mounted crystals, the fixed-target chip stage that rasters thousands of static crystals through the beam, the sample backlight and on-axis viewer for alignment, the beamstop, and the fast sample shutter. It is the heart of i24's novelty, and it changes the catalog by exactly nothing.

The chip stage is what makes i24 different from its rotation-MX sibling I03. There is no continuous omega sweep over one crystal and no sample-changing robot. Instead a chip holding thousands of static crystals is stepped across the beam, one diffraction snapshot per addressable window, hardware-sequenced on the PMAC controller with Zebra TTL gating.

## The vertical goniometer (reused Family)

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `Goniometer` | [`Goniometer`](../../../catalog/families.md) | `BL24I-MO-VGON-01:` | the vertical pin goniometer (dodal VerticalGoniometer); circle and pin-translation axes pending |

i24 reuses the catalog `Goniometer`, the Family I03 graduated with the Smargon micro-goniometer. The i24 unit is dodal's VerticalGoniometer, a vertical pin goniometer rather than a fresh device class, so no Family is coined. `Goniometer` stays a bare role-noun: distinct from `RotaryStage` (a single tomographic rotation axis carrying PSO fly-scan Following) and from `TiltStage` (a limited-range tilt with no primary rotation axis). The circle count and the pin-translation axes are carried pending (GONIO-1). In serial fixed-target collection the goniometer orients and aligns pin-mounted crystals; it does not perform the per-window rotation that rotation MX relies on, which is what the chip stage replaces.

## The fixed-target chip stage (the serial novelty)

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `ChipStage` | `LinearStage` | `BL24I-MO-CHIP-01:` | the fixed-target chip stage (dodal PMAC, an XYZ stage); positions the addressable chip across the beam |

This is the device that makes i24 a serial / fixed-target beamline, and the one CORA deliberately does not over-model. The chip stage is dodal's PMAC, an XYZ stage, so it reuses `LinearStage`: it is **not** a new `ChipStage` or `SerialStage` Family. The stage moves the chip; the chip is the addressable grid the stage rasters.

Two CORA modelling decisions are carried as questions rather than baked in:

- **The chip as a Fixture / Subject grid (CHIP-1).** The chip holds thousands of static crystals, rastered one window at a time. The stage is a `LinearStage` Asset; the chip itself, the addressable grid and its well or aperture map, is a Fixture, and the crystals it carries are Subjects. The grid map lives in beamline software, not a PV, so the addressing and how a collection window maps to a stage position are carried as the open CHIP-1, not invented here.
- **The serial raster seam (SSX-1).** The raster trajectory, the encoder position-compare, the per-window dwell, and the laser triggers run on the PMAC motion program. That sequencing is the orchestration seam CORA's edge replaces, driving through ophyd / EPICS, not a device Family. Whether the chip-raster fly-collection enters CORA's catalog as a serial-crystallography Capability is the deferred SSX-1. The PMAC-fired lasers are carried as a trigger setting on that seam, not a modelled device, pending LASER-1.

## The viewing and alignment devices

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `Backlight` | `Backlight` (loose) | `BL24I` | the dual sample backlight (dodal DualBacklight); sample illumination for on-axis viewing |
| `OnAxisViewer` | `Camera` | `BL24I-DI-OAV-01:` | the on-axis-view alignment camera with beam-centre file (dodal OAVBeamCentreFile) |

The dual backlight reuses I03's loose `Backlight` family: no existing Family carries an illumination affordance, so it stays loose and is earned only on a rule-of-three. The PV root `BL24I` and the backlight positions are pending (BACKLIGHT-1). The on-axis viewer reuses `Camera` for alignment imaging; its zoom and beam-centre configuration live in GDA files under `/dls_sw`, not in spine-owned PVs, so they are plumbing CORA observes rather than data it owns (CTRL-1).

## The beamstop and the sample shutter

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `Beamstop` | `BeamStop` | `BL24I-MO-BS-01:` | the positioned beamstop; axis roles pending |
| `SampleShutter` | `Shutter` | `BL24I-EA-SHTR-01:` | the fast sample shutter (dodal MXZebraShutter), Zebra-controlled |

The beamstop reuses `BeamStop`, a positioned beamstop on the sample axis; its axis roles are carried pending (OPT-2). The sample shutter reuses `Shutter`: it is the fast Zebra-controlled MXZebraShutter that gates the per-window exposure during the chip raster. That per-window gating is part of the serial-collection sequence, so the trigger timing is carried on the serial seam (SSX-1). The shutter Family is shared with the interlocked hutch photon shutter on the [Detector](detector.md) page; the hutch shutter's PSS permit structure is a separate question (PSS-1).

Whether the goniometer, chip stage, backlight, and beamstop compose a serial-endstation Assembly (the analogue of 2-BM's SampleTower) is deferred, as the other Diamond deployments deferred their Assemblies in descriptor mode: grouping is promoted only when a feature must act on the whole. The first cut is flat Assets.

See [Open questions](../questions.md) for the confirmations still needed and [Inventory](../inventory.md) for the Asset tree.
