# Sample

*The endstation sample side: the KB nanofocus that forms the coherent spot, the beam-conditioning unit, the sample goniometer, the positioning towers, and the endstation diagnostics. PVs verified against `cditools/motors.py` (KB / BCU / GON classes), `startup/18-screens.py`, `21-tdms.py`, `31-electrometers.py`.*

CDI focuses the coherent beam to a small spot with a Kirkpatrick-Baez mirror pair, conditions it through the beam-conditioning unit just before the sample, and records the far-field diffraction pattern. The sample side carries the focusing optic, the goniometer, and the endstation positioning towers; the real-space image is recovered offline by phase retrieval, a `ComputePort` leg, not modelled here.

| Asset | Family | PV | What it does |
| --- | --- | --- | --- |
| `KBMirror` | Mirror | `XF:09IDC-OP:1{Mir:KBv}` | KB nanofocus pair (VKB + HKB) forming the coherent spot |
| `ConditioningSlit` | Slit | `XF:09IDC-OP:1{Slt:BCUU}` | beam-conditioning-unit slits trimming the beam at the sample |
| `InlineCamera` | Camera | `XF:09IDC-BI{BCU-Cam:9}` | BCU inline beam-viewing camera |
| `Goniometer` | Goniometer | `XF:09IDC-OP:1{Gon:1}` | sample goniometer and stack |
| `SampleTower1` | LinearStage | `XF:09IDC-ES:1{TDMS:T1}` | endstation positioning tower 1 |
| `SampleTower2` | LinearStage | `XF:09IDC-ES:1{TDMS:T2}` | endstation positioning tower 2 |
| `DiamondBeamMonitor` | BeamPositionMonitor (loose) | `XF:09IDC-BI{BPM:1}` | transmissive diamond BPM ahead of the sample |
| `SampleCamera` | Camera | `XF:09IDC-BI{SMPL-Cam:10}` | sample-viewing camera |

## Forming and conditioning the coherent spot

The `KBMirror` is the focusing optic that makes CDI a nanofocus beamline: a vertical mirror (VKB) and a horizontal mirror (HKB) in the Kirkpatrick-Baez crossed geometry, each with pitch, roll, and yaw plus jack and translation axes, a defining slit, and a fluorescent screen, with an exit window after the pair. It focuses the coherent beam to the small spot the imaging needs, and reuses the `Mirror` family, the same binding the [FMX](../../fmx/equipment/sample.md) and SRX KB mirrors carry; the focal size and coating are KB-1.

The `ConditioningSlit` is the beam-conditioning unit (BCU): an upstream slit pair and a downstream slit pair that trim and guard the coherent beam just before the sample, with an `InlineCamera` on the same module for beam viewing. For a coherent-imaging beamline these slits are the coherence-conditioning hardware, so CORA models them as first-class `Slit` Assets rather than folding them into settings.

## The sample stack

The `Goniometer` is the sample goniometer and stack (`Gon:1`): sample lab-frame translations and rotations, with small-sample and large-sample axis sets and alignment axes, plus a sample-viewing screen. It reuses the `Goniometer` family; the orientation axes matter for Bragg CDI, where the sample is rocked around a Bragg peak. The full axis set is STAGE-1.

The `SampleTower1` and `SampleTower2` are the two endstation positioning towers (the source's TDMS towers), each carrying translation, camera, and angle axes. Which tower carries the sample and which carries the detector, and the sample-to-detector distance that sets the recorded q-range, are not settled in the public config (some tower axes are read-only pending commissioning), so they are folded into STAGE-1. Both reuse the `LinearStage` family.

## Endstation diagnostics

The `DiamondBeamMonitor` is a transmissive diamond beam-position monitor read through a TetrAMM electrometer, just ahead of the sample; in source it was repurposed from ion-chamber use to the diamond BPM. It binds the loose `BeamPositionMonitor` family (held; DIAG-1). The `SampleCamera` views the sample on-axis (a further endstation Prosilica sits alongside); it reuses `Camera`, and the live diagnostic set is CAM-1.
