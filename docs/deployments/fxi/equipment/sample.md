# Sample

*The TXM sample stage and the transmission-microscopy optics around it. All bind to the `XF:18IDB-OP` prefix, verified against `startup/11-txm_motor.py`.*

FXI places the specimen in a flooded monochromatic field and rotates it for tomography. The diffractive optics around the sample (condenser before it, zone plate and phase ring after it) are what make this a microscope rather than a parallel-beam scanner; they are the optics 2-BM does not have.

## The sample stage

The sample stack (`class TXMSampleStage`, instance `zps`) is the positioning core. It presents the `Positioner` Role.

| Axis | PV | Role |
| --- | --- | --- |
| `sx` | `XF:18IDB-OP{Env:1-Ax:Xl}Mtr` | sample translation X |
| `sy` | `XF:18IDB-OP{Env:1-Ax:Yl}Mtr` | sample translation Y |
| `sz` | `XF:18IDB-OP{Env:1-Ax:Zl}Mtr` | sample translation Z |
| `pi_r` | `XF:18IDB-OP{TXM:2-Ax:R}Mtr` | tomography rotation (theta) |

`pi_r` is the tomography rotation axis and the trigger master: the Zebra reads it as encoder `enc1` and emits position-compare pulses to the camera (see [Controls](controls.md)). This is the FXI analog of 2-BM's `Rotary` air-bearing stage. The hardware (air-bearing vs piezo), encoder resolution, and max speed are not in the profile collection; the "PI / Physik Instrumente" reading of the `pi_r` name is an inference, carried `confirm` (STAGE-2).

## The transmission-microscopy optics

These shape and analyze the beam through the sample. `Condenser`, `ZonePlate`, and `PhaseRing` are catalog Families (graduated with this deployment); `BetrandLens` stays a loose family name that renders as text, FXI-only (OPTIC-3).

| Optic | Family | PV axes | What it does |
| --- | --- | --- | --- |
| Condenser (`clens`) | Condenser | `{CLens:1-Ax:X/Y1/Y2/Z1/Z2/P}` | floods the sample with monochromatic beam |
| Aperture (`aper`) | Aperture | `{Aper:1-Ax:X/Y}`, `{TXM-Aper:1-Ax:Z}` | defines the illuminated field |
| ZonePlate (`zp`) | ZonePlate | `{ZP:1-Ax:X}`, `{BLens:1-Ax:Y}`, `{TXM-ZP:1-Ax:Z}` | the objective; magnifies the transmitted image |
| PhaseRing (`phase_ring`) | PhaseRing | `{PR:1-Ax:X/Y}`, `{TXM-PH:1-Ax:Z}` | Zernike phase contrast |
| BetrandLens (`betr`) | BetrandLens | `{BLens:1-Ax:X}`, `{ZP:1-Ax:Y}` | conoscopic alignment aid |

The zone plate is reported in source (`startup/20-global_param.py`) as a NanoTools plate, 244 um diameter, 30 nm outer zone width. These are code constants, not staff-verified (OPTIC-4).

!!! warning "Cross-wired Y axes"
    In source, `zp.y` is wired to the `{BLens:1-Ax:Y}` record and `betr.y` is wired to the `{ZP:1-Ax:Y}` record: the zone-plate and Bertrand-lens Y axes are cross-wired. This is preserved faithfully in the descriptor and recorded as a [Caution](../cautions.md); do not "correct" it without confirming the real wiring with FXI staff.

## Sample environment

A Lakeshore 336 temperature controller (`XF:18ID-ES{Env:01`) appears in source but is disabled (`motor_lakeshore = []`), so it is not modeled as a live device (ENV-1).
