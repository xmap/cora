# Sample

*The micro-goniometer, the sample-changing robot, the on-axis viewing, and the sample cooling. PVs verified against the fmx-profile-collection startup files.*

FMX mounts cryo-cooled protein crystals on a single-omega micro-goniometer, exchanged by a robot from a dewar, and viewed on-axis for loop centring.

| Asset | Family | PV | What it does |
| --- | --- | --- | --- |
| `Goniometer` | Goniometer | `XF:17IDC-ES:FMX{Gon:1}` | orients and centres the crystal |
| `Robot` | (Positioner Asset) | `XF:17IDC-ES:FMX{Gov:Robot}` | loads / unloads crystals from the dewar |
| `Backlight` | Backlight (loose) | `XF:17IDC-ES:FMX{Light:1}` | on-axis illumination for centring |
| `SampleCamera` | Camera | `XF:17IDC-ES:FMX{Cam:7}` | on-axis sample viewing |

## The goniometer

The `Goniometer` reuses the `Goniometer` family that Diamond i03 graduated (the Smargon): a single omega rotation (`XF:17IDC-ES:FMX{Gon:1-Ax:O}Mtr`) with GX / GY / GZ sample-centring, PY / PZ pin stages, and PI fine X / Y / Z scanners. This is the reuse point: a single-omega MX micro-goniometer is the same Family as i03's, axis count and centre-of-rotation a per-Asset settings difference, not a Family split (GONIO-1). FMX is the second sighting of the MX goniometer, reinforcing the graduation.

## The sample-changing robot

The `Robot` is the automated sample changer, coordinated by the LSDC Governor state machine (`XF:17IDC-ES:FMX{Gov:Robot}`) with a dewar / puck safety interlock (`XF:17IDC-OP:FMX{DewarSwitch}`). Following the i03 / 19-BM precedent, it is **one Positioner-presenting Asset, not a new SampleChanger Family**: it loads and unloads a `Subject` (the crystal), gated by a `Clearance`, with the vendor in a bound Model. The exchange workflow and the Subject custody lifecycle (Received to mounted to measured to Returned) are the genuinely new MX modelling, deferred to a named question (ROBOT-1).

## Sample environment

The on-axis illumination (`Backlight`, a ring light) reuses the loose `Backlight` family that i03 and i24 use; FMX is the third sighting, still held pending the fold-vs-promote decision (DET-1). Sample cryo-cooling (the cold-gas cryostream) is not exposed in the profile collection, which carries only an annealer / thaw-air actuator (`XF:17IDC-ES:FMX{Wago:}`), so the cooling is deferred (CRYO-1); it would bind `TemperatureController` (the i03 cryostream precedent) once its PV is supplied.
