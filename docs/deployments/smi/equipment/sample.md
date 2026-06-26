# Sample

*The experiment-hutch sample side: the grazing-incidence sample stack and the in-situ environment. PVs verified against `startup/smibase/manipulators.py` and `linkam.py`.*

SMI places a film or interface in the beam at a grazing angle for GISAXS / GIWAXS, or a bulk sample in transmission for SAXS / WAXS. The grazing-incidence geometry is what distinguishes SMI's sample side, and it is a sample-orientation variant, not a new device family.

| Asset | Family | PV | What it does |
| --- | --- | --- | --- |
| `BeamDefiningSlit` | Slit | `XF:12IDC-OP:2{Slt:C}` | trims the beam onto the sample |
| `GuardSlit` | Slit | `XF:12IDC-OP:2{Slt:E}` | cleans up parasitic scatter ahead of the sample |
| `SampleStage` | LinearStage | `XF:12IDC-OP:2{HUB:Stg}` | positions and orients the sample (grazing axes) |
| `SampleTemperature` | TemperatureController | `XF:12ID-ES{LINKAM}:` | in-situ thermal environment |

## Conditioning the beam onto the sample

The experiment hutch carries its own beam-defining and guard slits (`BeamDefiningSlit`, the C-hutch slit; `GuardSlit`, the E slit) just upstream of the sample: the defining slit trims the beam to the size a scattering measurement needs, the guard slit downstream cleans up the parasitic scatter it throws. Both reuse the `Slit` family. This mirrors the way Diamond [I22](../../i22/index.md) models its slit train as first-class Assets.

## The grazing-incidence sample stack

The `SampleStage` is the HUB stack: x / y / z translations plus theta / phi / chi orientation axes, with a SmarAct piezo (`XF:12ID2C-ES{MCS:2}`) for fine motion. The theta / phi / chi axes set the shallow incidence angle a grazing-incidence measurement needs, the GISAXS / GIWAXS geometry that an interface beamline lives on. CORA binds the stack to `LinearStage` as a design-phase placeholder; whether the orientation axes are modelled as a `Goniometer` plus an Assembly (the 8-ID / i11 precedent) is folded into STAGE-1.

## Sample environment

The `SampleTemperature` Linkam stage (with a tensile variant) reuses the `TemperatureController` family (graduated in #350); a LakeShore four-output controller serves alongside. Which units are live is TEMP-1.

Beyond temperature, SMI carries the in-situ soft-matter cells that are its specialty: a humidity cell (driven through Moxa analog IO, with the relative humidity computed in software rather than read from a dedicated PV) and a blade coater (a SmarAct stage plus a syringe pump) for studying films as they form. These would each need their own family or Procedure decision, so they are deferred (INSITU-1) rather than modelled at this design phase; they are named here so the reader knows the in-situ surface is not yet drawn.
