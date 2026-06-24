# Detector

*The detectors read per dwell point during a scan. PVs verified against `startup/20-detectors.py`, `20-eiger.py`, `21-xspress3.py`.*

A scanning-probe measurement is multi-modal: at each point of the raster, HXN reads several heterogeneous detectors at once. This is the new detector shape for CORA, distinct from the single imaging detector at FXI or 2-BM.

| Asset | Family | PV | Role in a scan |
| --- | --- | --- | --- |
| `FluorescenceSpectrometer` | EnergyDispersiveSpectrometer | `XF:03IDC-ES{Xsp:1}` | per-point X-ray fluorescence spectrum; element maps are fit downstream |
| `MerlinDetector` | Camera | `XF:03IDC-ES{Merlin:1}` | per-point diffraction frame for ptychography |
| `EigerDetector` | Camera | `XF:03IDC-ES{Det:Eiger1M}` | pixel detector for ptychography |
| `DexelaDetector` | Camera | `XF:03IDC-ES{Dexela:1}` | flat-panel for wide-field diffraction |
| `FluxCounter` | GenericProbe | `XF:03IDC-ES{Sclr}` | I0 / transmission counts for normalization |

## Reuse and the open roster

- The **fluorescence spectrometer** is an Xspress3 (4 channels in source, C1-C4) binding `EnergyDispersiveSpectrometer`, the catalog Family graduated once 2-ID and 7-BM shared it; HXN's is the third sighting. It presents the Sensor Role (a per-point spectrum is a Reading, not a 2D frame). Vendor and element count are pending (DET-1).
- The **pixel detectors** (Merlin, Eiger, Dexela) reuse the `Camera` Family, following the Diamond Eiger-to-Camera precedent: a pixel-array detector presents the Detector Role. XRF mapping and ptychography differ only by which of these is populated.
- Which detectors are physically installed and active is open (CAM-1): source carries Merlin (x2), Eiger 1M, and Dexela, with some classes duplicated behind a `USE_RASMI` switch; CORA models the live ones (`merlin1`, `eiger1`, `dexela1`) and excludes the dormant duplicates pending staff confirmation.

A single scanning Method would bind the fluorescence spectrometer, one pixel `Camera`, and the flux counters **together** as a heterogeneous per-point detector set, which no prior CORA deployment exercises.
