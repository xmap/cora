# Sample

*The KB nanofocus optics and the nano-endstation sample stack. PVs verified against `startup/16-nanoES.py` and `15-microES.py`.*

SRX focuses the beam to a submicron spot with a Kirkpatrick-Baez mirror pair and rasters the sample through it, the same scanning-probe acquisition HXN introduced, here serving XRF mapping, XANES maps, and XRF-tomography.

| Asset | Family | PV | Role |
| --- | --- | --- | --- |
| `NanoKBMirror` | Mirror | `XF:05IDD-ES:1{nKB}` | Kirkpatrick-Baez nanofocus mirror pair |
| `SampleStage` | LinearStage | `XF:05IDD-ES:1{nKB:Smpl}` | nano sample raster stack (the scan axes) |
| `SampleRotary` | RotaryStage | `XF:05IDD-ES:1{nKB:Smpl}` | sample rotation for XRF-tomography |
| `Attenuators` | Filter | `XF:05IDD-ES{IO:4}DO:` | pneumatic attenuator foils |
| `SampleTemperature` | TemperatureController | `XF:05IDD-ES{LS:1-Chan:}` | sample-environment thermal control |

## Reuse

The KB nanofocus reuses the `Mirror` Family (a KB pair is two mirrors, the same Family the optics-hutch mirrors use). The sample stack reuses `LinearStage`; the XRF-tomography rotation reuses `RotaryStage` (raster x rotation, the same family as 2-BM/FXI tomography and HXN nano-tomo). The thermal stage reuses `TemperatureController` (graduated in #350). The interferometric stage feedback (FPS, PICOSCALE) stays on the floor, the closed loop runs in EPICS below the ControlPort, as at HXN.

There is also a **micro endstation** (05IDB) with its own sample stack; this scaffold models the nano (KB) endstation and notes the micro endstation as deferred (ENDSTATION-1), the same way the 32-ID scaffold modelled one of several instruments.
