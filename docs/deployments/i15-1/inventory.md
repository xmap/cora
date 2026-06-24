# Inventory

*The CORA Asset model for I15-1: the planned device tree, the dodal-derived control handles, and what still needs confirming.*

I15-1 is a design-phase modelling exercise, so this is the planned Asset shape, not a registered inventory. It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages. The shape is generated-honest: it is authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i15-1/beamline.yaml) descriptor that the Source page renders from.

As at I22 and I03, the **control handles are known** (`BL15I` root, from dodal). Every device binds an existing catalog Family or a reused loose one: **I15-1 adds no new catalog kinds.** No vendor Model is bound.

## The Asset tree

Root Asset `I15-1` (`tier = Unit`, `facility_code = diamond`). Bold families are loose design-intent names reused from sibling deployments (they render as plain text). The PSS / gonio interlocks are **not** in this tree: they are the Enclosure `permit_signal` (INTERLOCK-1).

| Asset | Family | Control handle (dodal) | Notes |
| --- | --- | --- | --- |
| `I15-1` | (root) | | bound to the Diamond Site |
| `StorageRing` | **StorageRing** | | observe-only ring state; loose, reused from I22 |
| `LaueMono` | Monochromator | `BL15I-OP-LAUE-01:` | bent-Laue mono; energy is a read-only y-to-energy lookup readback |
| `M1` | Mirror | `BL15I-OP-MIRR-01:` | multilayer mirror |
| `Attenuator` | Filter | `BL15I-OP-ATTN-02:` | foil attenuator; 7 named transmission levels (Positioner + Indexable) |
| `AttenuatorSticks` | LinearStage | `BL15I-OP-ATTN-01:` | three-stick attenuator stage |
| `AttenuatorY` | LinearStage | `BL15I-OP-ATTN-02:Y` | attenuator vertical positioning |
| `Slit2`..`Slit5` | Slit | `BL15I-AL-SLITS-0N:` | beam-defining slits |
| `BeamStop` | BeamStop | `BL15I-MO-SMAR-02:` | positioned beamstop |
| `HutchShutter` | Shutter | `BL15I` (interlocked) | PSS-interlocked hutch safety shutter |
| `FastShutter` | Shutter | `BL15I-EA-ZEBRA-01:SOFT_IN:B3` | Zebra-driven fast shutter |
| `Rail` | Table | `BL15I-MO-RAIL-01:` | the shared sample-environment rail; existing Table Family, not a new Rail kind |
| `EnvX` | LinearStage | `BL15I-MO-TABLE-01:ENV:X` | the shared rail X the cobra / cryostream interchange on |
| `Blower` | LinearStage | `BL15I-EA-BLOWR-01:TLATE` | gas blower; SafeOrBeam = Positioner + Indexable SAFE/BEAM, not a TemperatureController |
| `Cobra` | LinearStage | `BL15I-MO-TABLE-01:ENV:X` | Oxford Cobra; SafeOrBeam; interchangeable with the cryostream |
| `Cryostream` | LinearStage | `BL15I-MO-TABLE-01:ENV:X` | Oxford Cryostream; SafeOrBeam; interchangeable with the cobra |
| `SampleTrans` | LinearStage | `BL15I-MO-TABLE-01:TRANS:` | sample x / y / phi |
| `Hexapod` | Hexapod | `BL15I-MO-HEX-01:` | six-axis sample hexapod |
| `BaseY` | LinearStage | `BL15I-MO-TABLE-01:Y` | sample table base height |
| `TwoTheta` | RotaryStage | `BL15I-MO-TABLE-01:TTH` | two-theta detector arm angle |
| `Robot` | (Positioner, deferred) | `BL15I-MO-ROBOT-01:` | powder/capillary changer; one Positioner Asset + Subject + Clearance (I03 shape), not a new Family |
| `Eiger` | Camera | `BL15I-EA-EIGER-01:` | Dectris Eiger area detector (Detector Role) |
| `Detector2` | LinearStage | `BL15I-EA-DET-02:` | second detector translation |
| `I0` | **FluxMonitor** | `BL15I-EA-JBPM-03:` | incident-flux monitor (TetrAMM); presents Sensor; loose, reused from I22 |
| `Zebra` | TimingController | `BL15I-EA-ZEBRA-01:` | FPGA trigger fan-out |

Reused catalog Families (no new Family needed): `Monochromator`, `Mirror`, `Filter`, `LinearStage`, `Slit`, `BeamStop`, `Shutter`, `Table`, `Hexapod`, `RotaryStage`, `Camera`, `TimingController`. Loose families reused from siblings: `StorageRing` and `FluxMonitor` (from I22). **No new family, loose or catalog, is coined** (the proposed `Rail` and `Interlock` families were both refuted: rail folds into Table, interlocks into the Enclosure permit). The robot presents the existing Positioner Role (I03 / 19-BM pattern), shape deferred.

## Pending confirmations

Every value below is reverse-engineered from dodal or inferred, awaiting the beamline team. Each is tracked by an [open question](questions.md); the answer lands in the descriptor and the row is removed.

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Hutch PSS permit signals | both enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Which hutch each device sits in | all devices | `unknown-pending-confirmation` | (ENC-1) |
| Source type and energy range | `StorageRing` / source | `unknown-pending-confirmation` | (SRC-1) |
| Bent-Laue energy: goto-command vs read-only selection | `LaueMono` | `unknown-pending-confirmation` | (ENERGY-1) |
| Optic calibration (crystal LUT, mirror coating, attenuator table) | `LaueMono`, `M1`, `Attenuator` | `unknown-pending-confirmation` | (OPT-1) |
| Storage-ring state modelling boundary | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| SafeOrBeam actuator shape + rail-interchange semantics | `Blower`, `Cobra`, `Cryostream` | `unknown-pending-confirmation` | (SAFEBEAM-1) |
| Rail Family and exchange semantics | `Rail` | `unknown-pending-confirmation` | (RAIL-1) |
| Flux-monitor modelling and beam-center | `I0` | `unknown-pending-confirmation` | (FLUX-1) |
| Robot Asset, Clearance gate, and puck custody lifecycle | `Robot` | `unknown-pending-confirmation` | (ROBOT-1) |
| Eiger calibration and two-theta arm geometry | `Eiger`, `TwoTheta`, `Detector2` | `unknown-pending-confirmation` | (DET-1) |
| Total-scattering Capability and Methods in scope | techniques | `unknown-pending-confirmation` | (TECH-1) |
| Hardware identity (serial numbers, asset tags) | all devices | `unknown-pending-confirmation` | (ID-1) |

Assertion-style questions that do not leave a value blank (the scope question SCOPE-1, the interlock-modelling decision INTERLOCK-1, and the attenuator-station topology ATTN-1) are on [Open questions](questions.md) without a placeholder here.
