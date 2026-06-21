# Endstations

*The two TomoWISE sample stations. Design-phase; values are TDR design targets.*

TomoWISE has two experiment stations in the experiment hutch, sharing one [detector gantry](detector.md). They are modelled as two sample-stage groups in the [descriptor](../inventory.md), each presenting the specimen to the beam in a different way.

An endstation here is a grouping label, not a modeled aggregate: each is a cluster of Equipment `Asset`s (the stages and optics tabled below) inside the experiment hutch. The hutch itself is the access-gated [Enclosure](../../../architecture/modules/enclosure/index.md) on a separate axis; at MAX IV its PSS signals are still pending (see [Open questions](../questions.md)).

## Microtomography endstation (~45 m)

The workhorse station: a fixed sample table about 45 m from the source carrying the rotation and positioning stack.

| Component | Family | Key specs (TDR target) | Model / status |
| --- | --- | --- | --- |
| Sample table | `Table` | fixed at 45 m, surface 390 mm above the beam; Xt +/-100 mm, Yt +50/-150 mm, beta tilt 1.2 deg | - |
| Rotary stage | `RotaryStage` | tomographic rotation to 1200 rpm, 1 mdeg, TTL encoder 3600 pulses/rev; trigger master clock (see [Controls](controls.md)) | RT100AX target (STAGE-1) |
| Sample positioning | `LinearStage` | Xs/Zs centring, +/-6 mm per axis, 0.1 um | XY150B-12 (STAGE-2) |
| Laminography tilt | `TiltStage` | 25 deg tilt axis for laminography, distinct from tomography rotation | - |
| Sample-side slits | `Slit` | 50 x 5 mm aperture above the rotation axis | JJ X-ray IB-C50-air reference |
| Fast shutter | `Shutter` | sample-side fast shutter | Arinax Colibri (<5 ms) / Innospexion (<10 ms) reference |
| Slip ring | `SlipRing` | 30 to 40 channels for continuous-rotation acquisition to 1000 rpm | Family not yet in catalog |

Optional modules the TDR anticipates (a horizontal-rotation loading rig for in-situ mechanics, a kHz tomography module) are not yet modelled; they join as confirmed.

## Nanotomography endstation (~49 m)

The high-resolution station: the KB mirror pair focuses the undulator beam for 200-nm-class cone-beam imaging.

| Component | Family | Key specs (TDR target) | Model / status |
| --- | --- | --- | --- |
| KB pair | `Mirror` | Kirkpatrick-Baez fixed-curvature graded-multilayer focusing mirrors at ~49 m, focal spot 205 x 196 nm at 30 keV | reused `Mirror` Family |
| Sample stage | `NanoPositioner` | nanotomography sample positioning; Abbe error compatible with 200-nm resolution | deferred to procurement (NANO-1); Family not yet in catalog |

The `Mirror` Family is reused for the KB pair: the focusing-versus-steering distinction is a setting, not a Family split. The KB pair and the nano sample stage are the only nano-specific hardware; the shared beam delivery and detector serve both stations.

See [Open questions](../questions.md) for the deferred items (nano stage, stage models) and [Inventory](../inventory.md) for the Asset tree.
