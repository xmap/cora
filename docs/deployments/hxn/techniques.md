# Techniques

*What CORA would run at HXN: the Capabilities and portable [Catalog](../../catalog/methods.md) Methods, bound through an NSLS-II [Practice](../nsls2/index.md#the-techniques-adapted-here).*

HXN does scanning nano-XRF mapping, ptychography, nano-tomography, and spectro-tomography, all variants of one act: raster the sample through the focus and read the per-point detectors. The big modeling question HXN raises is whether scanning and ptychography are new Capabilities or fit existing ones; this scaffold **defers** coining them, following the Diamond i03/i22 and 32-ID precedent (no new Capability coined for a design-phase reverse-engineered deployment until a real conduct-path consumes it).

| HXN technique | CORA expression | Earn-the-abstraction call |
| --- | --- | --- |
| Scanning XRF mapping | Method under `acquisition` (a raster of per-point spectra) | **Defer** coining a `scanning` Capability; trigger = first raster conduct-path, or a 2nd scanning beamline |
| Ptychography | the same raster with a `Camera` in the detector slot + offline reconstruction | **Defer**; ptychography is not its own Capability. The reconstruction is a `ComputePort` leg, not a beamline Method |
| Nano-tomography | [`tomography`](../../catalog/methods.md) | reuse; raster x rotation, the same family as 2-BM/FXI tomography |
| Spectro-tomography | compose `tomography` + energy change | reuse; do not coin `spectro_tomography` |
| XANES / energy change | [`beamline_energy_change`](../../catalog/methods.md) | reuse; but the HXN energy change co-moves the zone-plate refocus per element (ENERGY-1), a richer move than FXI's mono-only change |
| Alignment | [`alignment`](../../catalog/methods.md) | reuse (line-center, knife-edge, center-of-mass) |

The central new shape, **scanning-probe acquisition with multi-modal per-point detection**, is the strongest in-kind argument the catalog has seen for a `scanning` Capability (the raster *is* the measurement, not a frame at a fixed pose). It is held open deliberately, not because it is weak, but because the discipline is to coin a Capability when a conduct-path forces it, not at scaffold time. See the [Controls seam](equipment/controls.md#the-seam-cora-and-the-floor) for how CORA's conducting engine would run the raster over the ControlPort and the ptychographic reconstruction over the ComputePort.
