# Techniques

*What CORA would run at SRX, several techniques on one beamline, each a [Catalog](../../catalog/methods.md) Method bound through an NSLS-II [Practice](../nsls2/index.md#the-techniques-adapted-here). SRX exercises the multi-Capability-per-beamline shape.*

SRX is a microprobe that does much: it maps elements, scans absorption edges, reconstructs 3D element distributions, takes diffraction, and images. The point for CORA is that all of this reuses Capabilities and Families the fleet already has, the techniques compose from existing parts rather than forcing new vocabulary.

| SRX technique | CORA expression | Reuse note |
| --- | --- | --- |
| Scanning XRF mapping | a raster reading the `EnergyDispersiveSpectrometer` | the HXN scanning shape; `scanning` Capability deferred (ENERGY-1 cohort) |
| XANES | an energy sweep over the `EnergyAxis` | the BMM energy-scan question; `energy_scan` deferred |
| XRF-tomography | [`tomography`](../../catalog/methods.md), raster x rotation | reuse; XRF maps at each angle |
| Diffraction | a raster/exposure reading a `Camera` pixel detector | reuse; the technique is the detector choice |
| Full-field imaging | the PCO `Camera` | reuse; the FXI/2-BM imaging shape |
| Alignment | beam, KB, and slit tuning | reuse [`alignment`](../../catalog/methods.md) |

## The multi-Capability-per-beamline shape

SRX is the first deployment where one beamline carries several distinct techniques at once. In CORA terms, one Unit Asset presents the equipment for multiple Capabilities (imaging, scanning XRF, energy-scan spectroscopy, tomography, diffraction), and a measurement selects the Capability plus the detector(s) it needs from the shared set. Nothing here is new vocabulary: it reinforces that the Capability/Method layer composes, the same `tomography` Method that serves 2-BM serves SRX's XRF-tomography (with a different detector in the slot), and the `EnergyDispersiveSpectrometer` that BMM uses for transmission-reference fluorescence serves SRX's XRF mapping.

Two Capabilities stay deferred, exactly as their originating beamlines left them: `scanning` (HXN) and `energy_scan` (BMM). SRX reinforces the case for both without coining either, per the design-phase discipline. The reconstruction/fitting legs (XRF fitting, tomographic reconstruction) are `ComputePort` work, not beamline Methods.
