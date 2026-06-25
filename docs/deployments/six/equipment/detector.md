# Detector

*The energy-dispersive RIXS spectrometer arm, its photon-counting camera, and the counting electronics. First cut; PVs read from the profile collection, carried confirm.*

RIXS detection is the signature of SIX: a meters-long energy-dispersive spectrometer arm collects the scattered soft X-rays, disperses them by energy, and spreads the spectrum onto a photon-counting camera at the end of the arm, while counting electronics read the incident and drain currents. They are modelled in the detection stage of the [descriptor](../inventory.md).

The spectrometer arm binds a loose `SpectrometerArm` Family (no catalog Family fits a multi-chamber dispersive arm; the catalog `EnergyDispersiveSpectrometer` is a point Sensor, see [Model](../model.md#new-loose-families)); the camera reuses the catalog `Camera` Family and the counters `FluxMonitor`.

## Detection chain

| Device | Family | Design spec / note |
| --- | --- | --- |
| `RIXSSpectrometer` | `SpectrometerArm` (loose) | energy-dispersive arm: bridge truss (`BT:1`) + optics chamber (`3AA:1`) + detector chamber (`DC:1`); the arm angle selects momentum transfer (`RIXS-1`) |
| `RIXSCamera` | `Camera` | photon-counting RIXS camera with on-detector centroiding and isolinear curvature correction; Family decision is `RIXS-2` (`DET-1`) |
| `DetectorSlit` | `Slit` | detector-chamber baffle slit (`OPT-2`) |
| `Scaler` / `Electrometer` | `FluxMonitor` | counting scaler + Femto transimpedance electrometer for the I0 / drain channels (`DET-1`) |

The arm is three coupled chambers: the bridge truss carries it, the optics chamber holds the dispersing element (its `2T` is the dispersion arm), and the detector chamber positions the camera (its `2T` and `Z` set the detector angle and distance). The full chamber geometry, and whether the arm composes into an Assembly, is `RIXS-1`.

## Families

Reused from the catalog: `Camera` (the RIXS camera), `Slit` (the detector slit), and `FluxMonitor` (the scaler and electrometer). New at n=1: the `SpectrometerArm` Family for the dispersive arm, held loose until a second RIXS / dispersive-arm beamline earns it. Whether the photon-counting camera warrants its own Family (versus `Camera` with settings) is `RIXS-2`; the channel map is `DET-1`. See [Inventory](../inventory.md) for the Asset tree.
