# Sample

*The TomoWISE sample stage. Design-phase; values are TDR design targets.*

The sample stage is two experiment stations in the experiment hutch, sharing one [Detector](detector.md) gantry: a microtomography station (~45 m) and a nanotomography station (~49 m). They are modelled as two sample-stage groups in the [descriptor](../inventory.md), each presenting the specimen to the beam in a different way. Models named "(target)" are the TDR design selections, carried unbound until procurement confirms them.

## Microtomography endstation (~45 m)

The workhorse station: a fixed sample table about 45 m from the source carrying the rotation and positioning stack. The `Rotary` stage is also the trigger master clock (see [Controls](controls.md)).

| Device | Family | Target model | Design spec (TDR) |
| --- | --- | --- | --- |
| `SampleTable` | `Table` | (in-house) | fixed at 45 m, surface 390 mm below the beam; Xt +/-100 mm, Yt +50/-150 mm, beta tilt 1.2 deg |
| `Rotary` | `RotaryStage` | RT100AX (STAGE-1) | 1200 rpm, 1 mdeg, TTL encoder 3600 pulses/rev; trigger master clock |
| `SamplePositioning` | `LinearStage` | XY150B-12 (STAGE-2) | Xs/Zs centring, +/-6 mm per axis, 0.1 um |
| `LaminographyTilt` | `TiltStage` | (target) | 25 deg tilt for laminography, distinct from tomography rotation |
| `SampleSlit` | `Slit` | (target) | 50 x 5 mm aperture; JJ X-ray IB-C50-air reference design |
| `FastShutter` | `Shutter` | (target) | sample-side fast shutter; Arinax Colibri (<5 ms) / Innospexion (<10 ms) references |
| `SlipRing` | `SlipRing` | (target) | 30 to 40 channels for continuous-rotation acquisition up to 1000 rpm |

Optional modules the TDR anticipates (a horizontal-rotation loading rig for in-situ mechanics, a kHz tomography module) are not yet modelled; they join as confirmed.

## Nanotomography endstation (~49 m)

The high-resolution station: the KB mirror pair focuses the undulator beam for 200-nm-class cone-beam imaging. The sample manipulator is a six-axis stack on a granite support, conceptually like the microtomography endstation but about ten times more precise; it reuses the same Families (no `NanoPositioner` of its own). The rotary is the critical axis: its Abbe error from wobble and eccentricity must not exceed 100 nm at 100 mm sample height. Each axis names a "(target)" model carried pending procurement (NANO-1).

| Device | Family | Target model | Design spec (TDR Table 9.5) |
| --- | --- | --- | --- |
| `KB` | `Mirror` | (target) | KB pair, fixed-curvature graded-multilayer; focus 205 x 196 nm @ 30 keV, 196 x 80 nm @ 45 keV |
| `NanoGranite` | `Table` | (target) | granite support housing the KB optics, the manipulator, and the detector stage |
| `NanoTilt` | `TiltStage` | Huber 5202.80 | Tilt X, 2 deg, 5 mdeg; aligns the rotation axis to the beam |
| `NanoCoarseX` | `LinearStage` | Huber 5101.20 | Xt coarse, 50 mm; CoR alignment + flat field |
| `NanoCoarseY` | `LinearStage` | Huber 5103.A20-90 | Yt coarse, 50 to 100 mm; sample height |
| `NanoCoarseZ` | `LinearStage` | Zaber X-LDQ-AE | Zt long-travel, 250 to 300 mm, <0.5 um; into the KB focus, then toward the detector |
| `NanoRotary` | `RotaryStage` | RT100AS | Rot y, continuous, 1 mdeg, eccentricity <100 nm, TTL 3600/rev |
| `NanoSamplePositioning` | `LinearStage` | XY150B-12 | Xs/Zs centring, +/-6 mm, 0.1 um |

The KB pair and the sample manipulator are the only nano-specific hardware; the shared beam delivery and detector serve both stations.

See [Open questions](../questions.md) for the model bindings still to confirm and [Inventory](../inventory.md) for the Asset tree.
