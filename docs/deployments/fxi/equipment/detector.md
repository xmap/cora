# Detector

*The imaging detector: a scintillator-relay-camera system. PVs verified against `startup/10-area-detector.py`.*

The magnified transmitted image lands on a scintillator, which converts X-rays to visible light that a camera records. The structure is the same scintillator-relay anatomy as 2-BM's microscope; FXI's magnification comes from the zone plate rather than a microscope objective turret.

## The imaging path

| Element | Family | PV | Notes |
| --- | --- | --- | --- |
| Scintillator (`scint`) | Scintillator | `XF:18IDB-OP{Det:Lens` | scintillator-relay lens stage (X/Y/Z); material and thickness pending (DET-1) |
| Detector support (`DetU`/`DetD`) | LinearStage | (prefix pending, DET-2) | X/Y/Z rails; `DetU.z` is the sample-to-detector propagation distance |
| Camera | Camera | `XF:18ID1-ES{Kinetix-Det:1}` | the live imaging detector (Photometrics Kinetix) |

## The camera roster

Source instantiates several camera classes; CORA models **one** detector position until staff confirm which are physically installed and active (CAM-1).

| Instance | Class | PV | Status |
| --- | --- | --- | --- |
| `KinetixU` | Photometrics Kinetix | `XF:18ID1-ES{Kinetix-Det:1}` | the active instance; the modeled camera |
| `KinetixD` | Photometrics Kinetix | `XF:18ID1-ES{Kinetix-Det:1}` | placeholder, same PVs as `KinetixU` (source comment) |
| `MaranaU` / `MaranaD` | Andor Marana | `XF:18IDB-ES{Det:Marana1}` | both share one PV (placeholder pair) |
| `Andor` | Andor Neo2 | `XF:18IDB-BI{Det:Neo2}` | present in source |
| `detA1` | Manta | `XF:18IDB-BI{Det:A1}` | area camera |

Because the U/D pairs share identical PVs, registering two camera Assets per pair would be modelling the same hardware twice; CORA holds one position. Kinetix 22 mm vs 29 mm is distinguished at runtime by `max_size_x` (2400 vs 3200). The readout-config keys (`KINETIX`, `KINETIX22`, `MARANA-4BV6X`, `SONA-4BV6X`) are literal in source; vendor part numbers are inferred from class names and pending (CAM-2). An Oryx camera (`XF:18IDB-ES{Det:Oryx1}`) is commented out and recorded as decommissioned.

## Magnification

The total magnification is a computed axis:

```
Magnification = (DetU.z / zp.z - 1) * VLM
```

with the visible-light-microscope factor `VLM = 10` (`GLOBAL_VLM_MAG`, `startup/20-global_param.py`). It is derived from two real Z positions (the detector support `DetU.z` and the zone-plate `zp.z`) and has no PV of its own. The energy-change move (`move_zp_ccd_xh`, see [Recipes](../recipes.md)) co-moves the zone plate and detector to hold magnification constant across energy.
