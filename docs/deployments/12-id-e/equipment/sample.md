# Sample

*The sample positioning stage, the sample rotator, and the in-situ temperature environments at 12-ID-E. Scaffold; PVs read from the bluesky/BITS instrument config (`github.com/BCDA-APS/usaxs-bits`), carried confirm.*

The USAXS sample side places the specimen between the matched Bonse-Hart crystal stages: the collimator rocks the beam onto the sample, the analyzer rocks downstream of it (both are USAXS optics on the [Source](../beamline.md) walk, since the rocking-curve scan against the collimator is the USAXS measurement). At the sample itself, a positioning stage sets where the specimen sits in the beam, a rotator turns it, and one of two temperature controllers conditions the in-situ thermal environment. None of these is a new device class; each binds an existing catalog [Family](../../../catalog/families.md).

## The sample stack (12-ID-E)

| Device | Family | PV | Design spec / note |
| --- | --- | --- | --- |
| `SampleStage` | `LinearStage` | `usxLAX:` | sample positioning stage; which translation axes are mounted is `SAMPLE-1` |
| `SampleRotator` | `RotaryStage` | `usxPI:c867:c0:m1` | PI C-867 sample rotator (`SAMPLE-1`) |
| `LinkamStage` | `TemperatureController` | `usxLINKAM:tc1:` | Linkam T96 temperature stage; presents the `Regulator` Role (`TEMP-1`) |
| `Ptc10Controller` | `TemperatureController` | `usxTEMP:tc1:` | PTC10 multi-channel temperature controller; presents the `Regulator` Role (`TEMP-1`) |

## The positioning stage and rotator

The `SampleStage` binds the catalog `LinearStage` Family: it is a pure-translation positioning stage that sets where the specimen sits in the beam. Its precise axis set, and what is mounted on it for a given measurement, is `SAMPLE-1`.

The `SampleRotator` binds the catalog `RotaryStage` Family. It is the PI C-867 rotator on `usxPI:c867:c0:m1`, turning the sample about its own axis. This is the same Family the Bonse-Hart collimator and analyzer crystal stages bind on the [Detector](detector.md) side: the operative axis there is the crystal rocking rotation, here it is the sample rotation, and a rotary positioning stage is the shared anatomy. The vendor name (PI C-867) is carried because it is read from the config; the rotator's serial and physical mounting are not in the config and stay `SAMPLE-1`.

## In-situ temperature environment

Two temperature controllers serve the sample environment, and both bind the graduated catalog `TemperatureController` Family, presenting the `Regulator` Role:

- the Linkam T96 temperature stage on `usxLINKAM:tc1:`, and
- the PTC10 multi-channel temperature controller on `usxTEMP:tc1:`.

This is the same Family three Diamond beamlines and IXS already use for their sample environments, so 12-ID-E coins nothing new for thermal control. The two units' temperature ranges, the PTC10's channel count, and whether the Linkam and the PTC10 coexist on a single measurement or are exchanged depending on the sample is `TEMP-1`.

## Deferred: the in-situ load frame

An in-situ load frame exists in the beamline's device library (`loadframe.py`) but is **not** in the active instrument config, so CORA does not model it and coins no Family for it. No Family is earned for an un-instantiated device; the load frame is named here only so the reader knows the in-situ surface is not yet fully drawn (`LOADFRAME-1`).

## Why no new Family here

The sample side tempts no new device class. The positioning stage and the sample rotator are ordinary translation and rotation stages (`LinearStage`, `RotaryStage`). The Linkam and PTC10 are settable thermal regulators (`TemperatureController`), the same shape Diamond and IXS already carry. The one device that could read as novel, the in-situ load frame, is deferred rather than modelled (`LOADFRAME-1`).

See [Open questions](../questions.md) for the sample-side facts still to confirm, and [Inventory](../inventory.md) for the Asset tree.
