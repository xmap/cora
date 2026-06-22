# Endstations

*The two TomoWISE sample stations. Design-phase; values are TDR design targets.*

TomoWISE has two experiment stations in the experiment hutch, sharing one [detector gantry](detector.md). They are modelled as two sample-stage groups in the [descriptor](../inventory.md), each presenting the specimen to the beam in a different way.

## Microtomography endstation (~45 m)

The workhorse station: a fixed sample table about 45 m from the source carrying the rotation and positioning stack.

- **Sample table** (Family `Table`): fixed at 45 m, surface 390 mm below the beam, leaving space for sample environments. Coarse table motion Xt (+/-100 mm), Yt (+50/-150 mm), and a beta tilt (1.2 deg).
- **Rotary stage** (Family `RotaryStage`): tomographic rotation up to 1200 rpm, 1 mdeg resolution, with a TTL encoder emitting 3600 pulses per revolution. The TDR names the Lab Motion Systems RT100AX as the target model; CORA leaves the Model unbound until confirmed (STAGE-1). This stage is also the trigger master clock (see [Controls](controls.md)).
- **Sample positioning** (Family `LinearStage`): Xs/Zs centring, +/-6 mm per axis, 0.1 um resolution. Target model XY150B-12 (STAGE-2).
- **Laminography tilt** (Family `TiltStage`): a 25 deg tilt axis for laminography, distinct from tomography rotation.
- **Sample-side slits** (Family `Slit`): a 50 x 5 mm aperture above the rotation axis; JJ X-ray IB-C50-air reference design.
- **Fast shutter** (Family `Shutter`): a sample-side fast shutter; the TDR cites Arinax Colibri (<5 ms) and Innospexion (<10 ms) reference designs.
- **Slip ring** (Family `SlipRing`, not yet in the catalog): 30 to 40 channels for continuous-rotation acquisition up to 1000 rpm.

Optional modules the TDR anticipates (a horizontal-rotation loading rig for in-situ mechanics, a kHz tomography module) are not yet modelled; they join as confirmed.

## Nanotomography endstation (~49 m)

The high-resolution station: the KB mirror pair focuses the undulator beam for 200-nm-class cone-beam imaging.

- **KB pair** (Family `Mirror`): Kirkpatrick-Baez fixed-curvature graded-multilayer focusing mirrors at ~49 m, focal spot 205 x 196 nm at 30 keV. Reused from the `Mirror` Family; the focusing-vs-steering distinction is a setting, not a Family split.
- **Sample manipulator** (granite support + a six-axis stack): the TDR specifies it in full (Table 9.5), conceptually like the microtomography endstation but about ten times more precise. It reuses the same Families, not a `NanoPositioner` of its own: a tilt (`TiltStage`, Tilt X), coarse X/Y/Z translations (`LinearStage`: Xt, Yt, and a long-travel Zt that brings the rotation axis into the KB focus), a continuous rotary (`RotaryStage`, Rot y), and fine Xs/Zs centring (`LinearStage`). The rotary is the critical axis: its Abbe error from wobble and eccentricity must not exceed 100 nm at 100 mm sample height. Each axis names a "(target)" model carried pending procurement (NANO-1).

The KB pair and the sample manipulator are the only nano-specific hardware; the shared beam delivery and detector serve both stations.

See [Open questions](../questions.md) for the model bindings still to confirm and [Inventory](../inventory.md) for the Asset tree.
