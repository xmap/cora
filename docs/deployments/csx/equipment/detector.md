# Detector

*The coherent-scattering area detectors and the counting electronics. First cut; PVs read from the profile collection, carried confirm.*

CSX detection is coherent soft X-ray area detection: the custom FastCCD and the newer AXIS detector record the coherent-scattering and holography patterns through the TARDIS diffractometer, with a fast shutter gating the exposure and counting electronics reading the diode and I0 channels. They are modelled in the detection stage of the [descriptor](../inventory.md).

The detectors reuse the catalog `Camera` Family (the soft X-ray / overscan / background specifics are per-Asset settings), the scaler `FluxMonitor`, and the diode `GenericProbe`.

## Detection chain

| Device | Family | Design spec / note |
| --- | --- | --- |
| `FastCCD` | `Camera` | custom FastCCD coherent-scattering detector (`DET-1`) |
| `AxisDetector` | `Camera` | AXIS area detector (`DET-1`) |
| `DiagnosticCamera` | `Camera` | diffractometer beam-view diagnostic camera |
| `Scaler` | `FluxMonitor` | scaler / Struck MCS counting electronics for the diode and I0 channels (`DET-1`) |
| `DiffractometerDiode` | `GenericProbe` | diffractometer absorber / diode (`DET-1`) |
| `FastShutter` | `Shutter` | exposure fast shutter |

## Families

Reused from the catalog: `Camera` (the FastCCD, AXIS, and diagnostic camera), `FluxMonitor` (the scaler / MCS), `GenericProbe` (the diode), and `Shutter` (the fast shutter). The coherent / photon-counting behavior of the FastCCD is carried as per-Asset settings, not a new Family; the detector models and channel map are `DET-1`. See [Inventory](../inventory.md) for the Asset tree.
