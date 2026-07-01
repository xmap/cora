# Detector

*The autoranging USAXS photodiode, the incident and transmitted flux monitors and the counting scaler, and the pinhole SAXS and WAXS area detectors. First cut; PVs read from the instrument config, carried confirm.*

USAXS detection is point and current-integrating, not imaging: a single photodiode counts the transmitted intensity through an autoranging Femto transimpedance amplifier while a matched pair of Bonse-Hart crystal stages is rocked through the Bragg condition, building a rocking curve that resolves momentum transfer q far below the pinhole-SAXS regime (`USAXS-1`, `BONSE-1`). The collimator and analyzer crystal stages that set the angular axis are USAXS optics on the [Source](../beamline.md) walk; this page covers the detection chain they feed. The same instrument also runs pinhole SAXS and WAXS on area detectors, which read out per-pixel rather than integrating a current. They are modelled in the detection stage of the [descriptor](../inventory.md).

Every device here reuses a catalog Family. The autoranging photodiode, the I0 / I00 / I000 / TRD flux monitors, and the counting scaler all bind `FluxMonitor`; the SAXS and WAXS Pilatus area detectors bind `Camera`; and the detector translation stage binds `LinearStage`. Unlike IXS, which coined a loose `EnergyAnalyzer` Family for its diced crystal analyzer, this beamline coins **no loose Family**: the two devices that could tempt one, the Bonse-Hart crystal stages and the autoranging photodiode, both fit existing Families (see [Why FluxMonitor, not a new detector family](#why-fluxmonitor-not-a-new-detector-family) and [Model](../model.md)).

## Detection chain

| Device | Family | Design spec / note |
| --- | --- | --- |
| `PhotodiodeDetector` | `FluxMonitor` | the UPD photodiode, the primary USAXS detector; autoranging Femto transimpedance amplifier (DDPCA300) across several gain decades; amplifier `usxLAX:fem09:seq02:`, autorange `usxLAX:pd01:seq02:`, photocurrent `usxLAX:USAXS:upd`; the gain autorange is a device-state setting (`DET-1`) |
| `FluxMonitors` | `FluxMonitor` | I0 / I00 / I000 / TRD incident and transmitted flux monitors via Femto amplifiers (`usxRIO:fem02-05:seq01:`, `usxLAX:USAXS:I0` / `I00` / `I000` / `trd`), for normalization (`DET-1`) |
| `Scaler` | `FluxMonitor` | counting scaler (ScalerCH `usxLAX:vsc:c0` / `c1`, Struck SIS3820 `usxLAX:3820:`) that counts the amplifier channels (`DET-1`) |
| `DetectorStage` | `LinearStage` | USAXS and SAXS detector translation stages (`OPT-2`) |
| `SaxsDetector` | `Camera` | pinhole SAXS Pilatus area detector (`DET-1`) |
| `WaxsDetector` | `Camera` | WAXS Pilatus area detector on its translation (`waxsx` `usxAERO:m3` / `waxs2x` `usxAERO:m7`) (`DET-1`) |

The chain reads outward from the sample. For USAXS, the rocked analyzer crystal stage points the transmitted beam at the UPD photodiode, which the autoranging Femto amplifier reads as a current; as the rocking scan walks the intensity across several decades, the autorange shifts the amplifier gain so the photodiode tracks the full rocking curve in one pass (`DET-1`, `USAXS-1`). The I0 / I00 / I000 / TRD monitors read the incident and transmitted flux through their own Femto amplifiers for normalization, and the scaler counts the amplifier channels. Detection here is point and current-integrating, so there is no area readout on the USAXS axis: the q axis is built by rocking the crystals, not by dispersing the beam across a sensor. For pinhole SAXS and WAXS the same instrument switches to the Pilatus area detectors, which read out per pixel; the detector translation stage positions the USAXS and SAXS detectors and the WAXS detector rides its own translation. The amplifier / autorange / channel map, and whether each flux monitor is a separate Asset or an amplifier channel, is `DET-1`.

## Why FluxMonitor, not a new detector family

The UPD photodiode is the signature USAXS detector and the one device that most tempts a new family, so the reuse argument is worth making explicitly. It is a current-integrating point detector: a single photodiode read through an autoranging Femto transimpedance amplifier across several gain decades. That is the same anatomy as the I0 / I00 / I000 / TRD flux monitors, which are also photodiodes read through Femto amplifiers, and as the counting scaler that totals the amplifier channels. They differ only in role, the UPD being the science signal and the others being normalization monitors, and role is a Method concern, not a Family difference. This is the BMM precedent, where the ion-chamber quad electrometer is the primary XAS measurement detector yet binds the same `FluxMonitor` Family as an auxiliary monitor would, rather than coining a synonym for the primary case. The multi-decade gain autorange is a device-state setting on the one `PhotodiodeDetector` Asset, not a new device class (`DET-1`).

The second temptation is the rocking-curve measurement itself. The Bonse-Hart collimator and analyzer crystal stages bind the catalog `RotaryStage`: the operative axis is the crystal rocking rotation, and channel-cut versus multi-bounce is a per-Asset setting, not a new optic Family (`BONSE-1`). The rocking-curve scan that resolves q is an acquisition shape, a new Capability deferred as `USAXS-1`, not a device class. Those stages are part of the USAXS optics on the [Source](../beamline.md) walk; they are named here because the rocking scan is what gives the photodiode its signal.

The pinhole SAXS and WAXS detectors are conventional area detectors and bind the catalog `Camera`, reusing the existing scattering anatomy with no new family (`DET-1`).

The net result is zero new families on the detection axis. The novelty of this beamline, the angular rocking fly-scan with a multi-decade autoranging point detector, lands as a new Capability and an acquisition shape, not as new device classes (`USAXS-1`, `BONSE-1`).

## Families

Reused from the catalog: `FluxMonitor` (the UPD photodiode, the I0 / I00 / I000 / TRD monitors, and the counting scaler), `Camera` (the pinhole SAXS and WAXS Pilatus area detectors), and `LinearStage` (the detector translation stage). No new family is coined on the detection axis, and nothing graduates; the catalog is unchanged. The autoranging gain and the amplifier / channel map are the open detail (`DET-1`). See [Inventory](../inventory.md) for the Asset tree and [Model](../model.md) for the no-new-family argument across the whole instrument.
