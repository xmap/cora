# XFM

*X-ray Fluorescence Microprobe at NSLS-II, beamline 4-BM: a scanning-XRF microprobe that rasters a sample through a focused bending-magnet beam and reads element maps on a multi-element silicon-drift detector, with a Maia continuous-mapping array. This page describes how CORA would model and run XFM; the model is reverse-engineered from public configuration, not yet confirmed by XFM staff.*

| Property | Value |
| --- | --- |
| Asset | `XFM` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 4` (PV namespace `XF:04BM*`; the endstation zone is `XF:04BMC`) |
| Institution | Brookhaven National Laboratory (context; not modeled as an Asset or Facility) |
| Status | Reverse-engineered from public config (design-phase scaffold) |
| Source | 4-BM bending magnet (not an insertion device) |

!!! note "How CORA would land on XFM"
    These pages describe how CORA would model, govern, and conduct XFM, the fifteenth NSLS-II beamline after [FXI](../fxi/index.md), [HXN](../hxn/index.md), [BMM](../bmm/index.md), [SRX](../srx/index.md), [SIX](../six/index.md), [CHX](../chx/index.md), [CSX](../csx/index.md), [XPD](../xpd/index.md), [ESM](../esm/index.md), [SMI](../smi/index.md), [IXS](../ixs/index.md), [SST](../sst/index.md), [ISS](../iss/index.md), and [FMX](../fmx/index.md). They are not a survey of the beamline's current software. The hardware facts are read from public NSLS-II open source (the `NSLS2/xfm-profile-collection` bluesky / ophyd startup files), which is **endstation-only**: the raster stage and detectors carry real PVs, but the bending-magnet source, the monochromator, the focusing optic, and the shutters are not in the profile and are carried `confirm` with no PV ([Open questions](questions.md)). This is a design-phase scaffold: the descriptor and these docs, with scenarios deferred.

## The defining shape: scanning XRF, pure reuse

XFM is a **scanning X-ray fluorescence microprobe**: it rasters a sample through a focused spot and reads the fluorescence spectrum at each point to build element maps, with a Maia array for fast continuous (fly-scan) mapping. It is CORA's second scanning-XRF beamline, after [2-ID](../2-id/index.md), and a **pure-reuse** deployment: it coins no Family and graduates nothing. The multi-element silicon-drift detectors reuse `EnergyDispersiveSpectrometer`, the raster stage `LinearStage`, the scaler I0 channels `FluxMonitor`, and the bending-magnet source the loose `Beam` PhotonBeam supply (the 2-BM / BMM precedent). XFM is the second consumer of the pending `scanning_fluorescence_microscopy` Method (2-ID was first), which strengthens but does not coin it (the energy_scan deferral discipline). It is a genuinely thin model: the public profile exposes only the endstation, so the optics are carried confirm-only.

## The beamline

Along the beam, in order:

- [Source](beamline.md): the bending-magnet source and the front-end / photon shutters, then the optics, the monochromator, the focusing optic, and the beam-defining slits (the optics carried confirm-only).
- [Sample](equipment/sample.md): the UTS raster scanning stage.
- [Detector](equipment/detector.md): the Xspress3 silicon-drift fluorescence detector, the Maia continuous-mapping array, and the scaler flux channels.

Cutting across all three:

- [Controls](equipment/controls.md): the scaler-counted raster, the Maia fly-scan, and the seam with the floor.

The cross-cutting reference view is the [Inventory](inventory.md).

## Techniques

[Techniques](techniques.md): the scanning XRF mapping XFM runs (and the XANES leg it could), and why the Method stays pending.

## Governance

[Governance](governance.md): who may act at XFM and the trust shape CORA applies; CORA brings its own per-Actor authority.

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's XFM content lives, and why XFM graduates nothing.
