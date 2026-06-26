# Sample

*The raster scanning stage that makes the XRF maps. PV verified against the xfm-profile-collection startup files.*

XFM's sample stage is the scanning instrument: it moves the sample through the focused microprobe spot, point-by-point for a step map or continuously for a Maia fly map.

| Asset | Family | PV | What it does |
| --- | --- | --- | --- |
| `SampleStage` | LinearStage | `XF:04BMC-ES:2{UTS:1-Ax:}` | rasters the sample through the focused spot |

## The raster stage

The `SampleStage` is the UTS X / Y / Z stage (`XF:04BMC-ES:2{UTS:1-Ax:X / Y / Z}Mtr`); it reuses the `LinearStage` family, the same scanning-stage Family that 2-ID and SRX bind for their XRF rasters. The scan is the measurement: at each stage position the fluorescence detectors are read, building a 2D element map (the X / Y plane) at a chosen Z standoff. A coarse / fine piezo split, if any, is not distinguished in the profile and is carried to confirm. Whether an additional rotation axis exists (which would enable XRF-tomography, the SRX shape) is not in the profile, so XRF-tomography is out of scope here (TECH-1).

The sample environment beyond the stage (in-situ cells, thermal control) is not exposed in the profile collection and is not modelled at this design phase.
