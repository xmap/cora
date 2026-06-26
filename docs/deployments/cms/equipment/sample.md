# Sample

*The endstation sample side: the sample-orientation goniometer, the surface-leveling stage, the sample-exchange arm, and the in-situ thermal / tensile stage. First cut; PVs read from the `NSLS2/cms-profile-collection` startup files, carried confirm.*

CMS places a film, an interface, or a bulk sample in the beam in the `cms-endstation` enclosure (`XF:11BMB`, `ENC-1`): at a shallow grazing angle for GISAXS / GIWAXS, in transmission for SAXS / WAXS / MAXS, or at a stepped specular angle for X-ray reflectivity (XR). The sample side is what sets the scattering geometry; every axis here reuses a catalog [Family](../../../catalog/families.md), and nothing on this page coins a new one. They are modelled in the sample stage of the [descriptor](../inventory.md).

## The sample side at a glance

| Asset | Family | PV | What it does |
| --- | --- | --- | --- |
| `SampleGoniometer` | `Goniometer` | `XF:11BMB-ES{Chm:Smpl}` | orients the sample: x / y plus theta (sth), chi (schi), phi (sphi); sth is the grazing-incidence and the specular-reflectivity angle (`SAMPLE-1`) |
| `SurfaceStage` | `TiltStage` | `XF:11BMB-ES{SM:1}` | surface-leveling tilts that bring a thin film flat to the beam (`SAMPLE-1`) |
| `SampleExchangeArm` | `LinearStage` | `XF:11BMB-ES{SM:1-Ax:Z}` | the GIBar sample-exchange arm: x / y / z plus yaw, loading a sample bar onto the goniometer (`ROBOT-1`) |
| `TemperatureStage` | `TemperatureController` | the Linkam thermal / tensile stage | in-situ temperature and tensile environment (`TEMP-1`) |

## Orienting the sample

The `SampleGoniometer` is the heart of the sample side. It carries the in-plane x / y translations and the three orientation axes, theta (sth), chi (schi), and phi (sphi), that set how the sample faces the beam. The sth axis does double duty: it is both the grazing-incidence angle that a GISAXS / GIWAXS measurement rides on and the specular angle that an XR scan steps through. It reuses the catalog `Goniometer` Family, the sample-orientation anatomy shared across the scattering fleet, so CMS adds no device here.

Two quirks live on this stage and are modelled as bindings rather than new structure. Staff have at times swapped sth and schi, and the `beamline_stage` configurations rebind the logical axes across the physical PVs at startup. CORA models the logical `Goniometer`, the orientation roles sth / schi / sphi, and treats which physical PV each logical axis is bound to as a setting on the Asset, not a separate Family per wiring. Which logical-to-physical binding is live for a given run is `SAMPLE-1`.

The `SurfaceStage` complements the goniometer for thin-film work: surface-leveling tilts that bring an interface flat to the beam before the grazing geometry is set. It reuses the catalog `TiltStage` Family. Whether the leveling tilts and the goniometer orientation axes are one fused Asset or two siblings on their separate PV roots is `SAMPLE-1`.

## Loading the sample

The `SampleExchangeArm` is the GIBar sample-exchange arm: a multi-axis loader, x / y / z plus yaw, that carries a sample bar onto the goniometer. For this first cut it is modelled by its stage axes and binds the catalog `LinearStage` Family, the same pure-translation anatomy the fleet sample stacks reuse. This is the one device on the sample side that is genuinely new in kind, a sample-handling robot rather than a positioning stage, but at n=1 a single fleet sample robot does not earn an abstraction. So no `SampleExchanger` Family is coined; the arm is carried as its axes, and the family decision is deferred (`ROBOT-1`) until a second fleet sample robot earns it. It is named here so the reader knows the handling surface is acknowledged, not yet drawn.

## Sample environment

The `TemperatureStage` is the Linkam thermal / tensile stage, the in-situ environment that lets CMS follow a soft-matter or thin-film sample as temperature or strain is varied. It reuses the catalog `TemperatureController` (Regulator) Family. Which units of the thermal / tensile environment are live for a given configuration is `TEMP-1`.

## Specular reflectivity reuses this stage

XR is a [Method](../../../catalog/methods.md), not a device. There is no physical two-theta detector arm on the CMS sample side: the area detector stays fixed and the "two-theta" is synthetic, a software region-of-interest that slides across the fixed Pilatus face to where the reflected beam lands as sth is stepped. So an XR scan reuses exactly the hardware already on this page and the [Detector](detector.md) side: the `SampleGoniometer` (sth) steps the specular angle, the Pilatus reads the reflected beam over a tracked region, and the incident flux is read by a `FluxMonitor`. No two-theta arm, no point detector, and no new device is coined for reflectivity (`XR-1`). The reflectivity Method is shared with i10 (its soft X-ray RASOR sibling); CMS is the second consumer.

## Why no new Family here

The sample side reuses the catalog throughout: `Goniometer` for orientation, `TiltStage` for surface leveling, `LinearStage` for the exchange arm, and `TemperatureController` for the in-situ thermal / tensile environment. This is reinforcement, not novelty: CMS's grazing-incidence and transmission scattering vocabulary is the direct NSLS-II twin of SMI, and it shares the same sample-side Families with the wider fleet. The one genuinely new thing on this page is the GIBar sample-exchange arm, and CORA deliberately does not coin a `SampleExchanger` Family for it at n=1; the arm is modelled by its stage axes and the family decision is held until a second sample robot earns it (`ROBOT-1`). Nothing here graduates and the catalog is unchanged.

See [Open questions](../questions.md) for the sample-side facts still to confirm, [Inventory](../inventory.md) for the Asset tree, [Model](../model.md) for the family-reuse rationale, and [the source walk](../beamline.md) for the PVs as read from the profile collection.
