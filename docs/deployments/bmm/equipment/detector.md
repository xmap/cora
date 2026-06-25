# Detector

*The XAS detectors read at each energy point. PVs verified against `startup/BMM/user_ns/detectors.py`.*

XAS is measured two ways, and BMM does both. The detectors here are the primary signal, sampled once per energy step of the scan.

| Asset | Family | PV | Role in a scan |
| --- | --- | --- | --- |
| `IonChambers` | FluxMonitor | `XF:06BM-BI{EM:1}EM180:` | I0 (incident), It (transmitted), Ir (reference) currents |
| `FluorescenceSpectrometer` | EnergyDispersiveSpectrometer | `XF:06BM-ES` | fluorescence yield from the sample (dilute samples) |
| `ScalerCounter` | GenericProbe | `XF:06BM-ES:1{Sclr:1}` | scaler / point counter for alignment |

## Transmission XAS

The `IonChambers` are a quad electrometer (class `BMMQuadEM`) reading three ion chambers: `I0` before the sample, `It` after it, and `Ir` after the reference foil. Transmission absorption is `ln(I0/It)` versus energy; the reference channel `ln(It/Ir)` gives a simultaneous known-edge spectrum for energy calibration.

These ion chambers are the **primary measurement detector** here, not auxiliary flux monitors, but they are the same device kind as the `FluxMonitor` Family (graduated in #353 from the Diamond i03/i15-1/i22 ion chambers), which BMM reuses rather than coining a synonym. The role nuance (primary signal vs auxiliary monitor) is a Method concern, not a Family difference; the gas fill and per-channel bindings are the open detail (DIAG-1).

## Fluorescence XAS

For dilute samples, the absorption is measured as fluorescence yield: the `FluorescenceSpectrometer` (an Xspress3, available in 1-, 4-, and 7-element configurations in source) records the fluorescence spectrum per energy point, and the element line of interest is integrated. It reuses the catalog `EnergyDispersiveSpectrometer` Family (graduated once 2-ID and 7-BM shared it), presenting the Sensor Role. Which element count is the installed default, and the vendor, are pending (DET-1).
