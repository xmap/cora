# Detector

*The coherent-diffraction area detectors. PVs verified against `startup/30-area-detectors.py` and `cditools/eiger_async.py` / `merlin_async.py`.*

CDI's measurement lives on its area detectors. A coherent-imaging measurement records the far-field diffraction pattern of the coherent spot: a single frame for forward CDI, a scan of overlapping frames for ptychography, or a rocking series for Bragg CDI. The real-space image is then recovered offline by phase retrieval.

| Asset | Family | PV | Role |
| --- | --- | --- | --- |
| `EigerDetector` | Camera | `XF:09ID1-ES{Det:Eig1}` | primary coherent-diffraction / ptychography detector |
| `MerlinDetector` | Camera | `XF:09ID1-ES{Det:Merlin1}` | second coherent-diffraction detector |

## Two photon-counting detectors

The `EigerDetector` (an Eiger2) and the `MerlinDetector` are both photon-counting area detectors: their low noise and single-photon sensitivity suit the weak, high-dynamic-range speckle of a coherent-diffraction pattern. Which one is primary for which technique (the larger Eiger2 for ptychography maps, the Merlin for fine Bragg-CDI work, or some other split) is not stated in the public config, so that is a staff question (DET-1), along with whether a direct-beam beamstop is installed (none is in source).

## Reuse, not new vocabulary

This is the reinforcement point of CDI as a CORA exercise: a coherent-imaging beamline with two photon-counting area detectors that needs **no new Family**. Both detectors reuse `Camera`, the Eiger-to-Camera precedent the fleet already carries at [CHX](../../chx/equipment/detector.md) (three Eigers) and [HXN](../../hxn/equipment/detector.md) (a Merlin and an Eiger for ptychography). A coherent area detector recording a diffraction pattern under a gated exposure is the same shape across all three; CDI shows it porting to a dedicated imaging beamline unchanged.

The one honest gap is the exposure gating: how the detector frames are triggered and synchronized with the scan is not in the profile collection (there is no trigger box), so it is carried as the headline controls question (TIMING-1, see [Controls](controls.md)). The detectors carry internal and external trigger modes in their device classes, but the floor chain that drives them is unknown.
