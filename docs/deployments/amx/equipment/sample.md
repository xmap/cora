# Sample

*The micro-goniometer, the automated EMBL robot, and the on-axis viewing. PVs verified against the amx-profile-collection startup files.*

AMX mounts cryo-cooled protein crystals on a single-omega micro-goniometer, exchanged by an automated EMBL robot from a 48-position dewar, and viewed on-axis for loop centring.

| Asset | Family | PV | What it does |
| --- | --- | --- | --- |
| `Goniometer` | Goniometer | `XF:17IDB-ES:AMX{Gon:1}` | orients and centres the crystal |
| `Robot` | (Positioner Asset) | `XF:17IDB-ES:AMX{EMBL}:` | loads / unloads crystals from the dewar |
| `SampleCamera` | Camera | `XF:17IDB-ES:AMX{Cam:7}` | on-axis sample viewing |

## The goniometer

The `Goniometer` reuses the `Goniometer` family that Diamond i03 graduated and FMX reused: a single omega rotation (`XF:17IDB-ES:AMX{Gon:1-Ax:O}Mtr`) with GX / GY / GZ sample-centring and PY / PZ pin fine stages. AMX is the third sighting of the MX goniometer, reinforcing the graduation; axis count and centre-of-rotation are a per-Asset settings difference (GONIO-1).

## The sample-changing robot

The `Robot` is the automated EMBL sample changer (`XF:17IDB-ES:AMX{EMBL}:`), coordinated by the LSDC / mxtools Governor state machine with a 48-position dewar and a sample-detection smart magnet. Following the i03 / 19-BM / FMX precedent, it is **one Positioner-presenting Asset, not a new SampleChanger Family**: it loads and unloads a `Subject` (the crystal), gated by a `Clearance`, with the vendor in a bound Model. The exchange workflow and the Subject custody lifecycle (Received to mounted to measured to Returned) are the genuinely new MX modelling, deferred to a named question (ROBOT-1). Being "highly automated", AMX is where this autonomous loop matters most.

## Sample environment

The on-axis sample viewing uses the `SampleCamera` (a Prosilica; low-mag and X-eye cameras serve alignment); AMX exposes no separate on-axis backlight PV (an FMX-vs-AMX difference). Sample cryo-cooling (the cold-gas cryostream) is not exposed in the profile collection, so it is deferred (CRYO-1); it would bind `TemperatureController` (the i03 cryostream precedent) once its PV is supplied.
