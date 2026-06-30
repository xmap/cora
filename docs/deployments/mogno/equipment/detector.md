# Detector

*The detector chain that records the transmitted cone beam, and the cone-beam magnification axis. First cut, from papers, models carried confirm.*

MOGNO records projections with two detection paths: a direct high-Z photon-counting detector for hard X-rays, and an indirect chain (a scintillator coupled through a microscope to an sCMOS camera) for higher spatial resolution. The cone-beam magnification, set by where the sample sits along the diverging beam, is modelled as a virtual axis because it is the working point that ties resolution and field of view together across the two stations.

## Devices

| Asset | Family | Note |
| --- | --- | --- |
| `Camera` | Camera | The imaging detector. The facility page names a Pimega (Si, photon-counting, in-house/PiTec), a PCO Edge 4.2 sCMOS, and a CdTe Medipix/Mobipix; the software paper refers only to a generic AreaDetector. Which detectors are installed and active at each station is uncertain in public sources (CAM-1). Vendor models are not bound. |
| `Scintillator` | Scintillator | The scintillator for the indirect chain (e.g. LuAG:Ce), coupled to the sCMOS via an Optique Peter microscope. Material, thickness, and the objective set pending (CAM-2). |
| `Magnification` | PseudoAxis | The cone-beam geometric magnification, set by the sample position along the diverging cone between the secondary source and the detector (the "zoom" tomography axis). A virtual axis over the sample and detector distances; rule pending (MAG-1). The FXI Magnification precedent. |

## One detector position, until staff confirm

The public sources name a roster of detectors but do not pin which are physically installed and active per station, so CORA models one detector position bound to `Camera` (plus the indirect-chain `Scintillator`) until staff confirm the configuration. This is the FXI multi-camera precedent: name the family, defer the exact roster to confirmation (CAM-1). See [Open questions](../questions.md#detector-and-data).

## Data of record

Each acquisition produces a single main data file carrying the projections plus flat and dark fields and a metadata dictionary (the software paper describes metadata collected via soft IOCs and injected into the file). The exact format (HDF5 / NeXus / DXchange `exchange` layout) is not stated in public sources (DATA-1). CORA keeps its own data of record (the PG event store); the beamline's data file and the downstream `ssc-raft` reconstruction (see [Model](../model.md#the-compute-axis-reconstruction-named-not-built)) are a source CORA observes, not a system it depends on.
