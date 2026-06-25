# Detector

*The RSoXS scattering detector and flux monitors (soft), and the HAXPES electron analyzer and ion chamber (tender). First cut; PVs read from the config-driven profile, carried confirm.*

SST detects two ways, one per branch: the SST-1 soft branch records scattered photons on the Greateyes WAXS area detector with incident-flux monitors, and the SST-2 tender branch records photoelectrons on the Scienta SES hemispherical analyzer with an ion chamber. They are modelled in the detection stage of the [descriptor](../inventory.md).

The WAXS detector reuses the catalog `Camera` Family and the flux monitors `FluxMonitor`. The Scienta SES is the device that **graduates** the `ElectronAnalyzer` Family (the 2nd hemispherical electron analyzer after ESM; see [Model](../model.md#what-this-deployment-graduates)).

## RSoXS detection (SST-1)

| Device | Family | Design spec / note |
| --- | --- | --- |
| `WAXSDetector` | `Camera` | Greateyes GE 4k4k WAXS scattering CCD (areaDetector); the SAXS twin is not instantiated (`DET-1`) |
| `AuMeshMonitor` | `FluxMonitor` | Au-mesh I0 monitor, single ADC channel (`DET-1`) |
| `IzeroPhotodiode` | `FluxMonitor` | Izero photodiode on the DMR I400 electrometer, channel IC3 (`DET-1`) |

## HAXPES detection (SST-2)

| Device | Family | Design spec / note |
| --- | --- | --- |
| `ElectronAnalyzer` | `ElectronAnalyzer` | Scienta SES hemispherical analyzer; pass-energy / lens-mode / kinetic-energy controls; graduates the Family (`PES-1`) |
| `IonChamber` | `FluxMonitor` | I400 electrometer ion-chamber channel (DM7); only the one channel is instantiated (`DET-1`) |

## Families

Reused from the catalog: `Camera` (the WAXS CCD) and `FluxMonitor` (the Au-mesh, photodiode, and ion chamber). Graduated with this deployment: `ElectronAnalyzer`, for the Scienta SES, earned once SST became the second photoemission beamline after ESM. The photoemission measurement is electrons out, not photons, so the analyzer is distinct from the photon detectors; analyzer model and lens / pass-energy controls are `PES-1`, and the detector channel sets are `DET-1`. See [Inventory](../inventory.md) for the Asset tree.
