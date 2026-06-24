# Sample

*The focusing optics that form the nano-spot and the sample stack rastered through it. PVs verified against `startup/13-mll.py` and `15-zp.py`.*

HXN focuses the beam to a nano-spot two ways, and scans the sample through it. This scanning geometry, the sample axes *are* the measurement, is what distinguishes HXN from the full-field [FXI](../../fxi/index.md).

## The two focusing optics

| Optic | Family | What it does |
| --- | --- | --- |
| `ZonePlate` | `ZonePlate` | a circular Fresnel zone plate focusing in 2D as one element |
| `MLL_Vertical` / `MLL_Horizontal` | `MultilayerLaueLens` (loose) | a crossed pair of 1D linear-zone lenses giving 2D focus |

The multilayer Laue lens binds a **loose family name** (`MultilayerLaueLens`): HXN is its only sighting, and it is geometrically distinct from the `ZonePlate` (1D linear vs 2D circular, run as a crossed `vmll` + `hmll` pair), so it is not folded into `ZonePlate`. It graduates into the catalog only at a second sighting (OPTIC-3). Whether both optics are permanently installed and operator-selected, or one is decommissioned, is a staff question (OPTIC-1).

Each optic carries an order-sorting aperture (`ZonePlateAperture`, `MLLAperture`, both `Aperture`) and the zone plate a central beam stop (`ZonePlateBeamStop`, `BeamStop`) to clean the focus.

## The sample stack

| Asset | Family | Axes / PV | Role |
| --- | --- | --- | --- |
| `SampleStage` | LinearStage | `ssx`/`ssy`/`ssz` on `XF:03IDC-ES{Ppmac:1}` | the fine raster axes (the scan trajectory) |
| `SampleRotary` | RotaryStage | `sth` on `XF:03IDC-ES{ANC350:1-Ax:0}` | tomographic rotation |
| `SamplePod` | Hexapod | `XF:03IDC-ES` (SmarAct Smarpod) | 6-DOF coarse pod |

The fine `ssx`/`ssy`/`ssz` axes (on the Power PMAC) are what a 2D fly-scan map drives, hardware-gated point by point by the [Zebra](controls.md). Coarse positioning sits on the Attocube ANC350 controllers. `SampleRotary` combined with the raster gives nano-tomography. The SmarAct Smarpod reuses the `Hexapod` Family as a single coordinated parallel-kinematics move, pending confirmation that the fit holds (STAGE-2).
