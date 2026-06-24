# Detector

*The energy-dispersive fluorescence detector in the 2-ID-D hutch. Design-phase; values carried as confirm.*

The detector modelled here is what makes 2-ID-D a different shape from the tomography pilots: not a full-field imaging camera, but an energy-dispersive detector that records an X-ray fluorescence spectrum at each scan point. Element maps are fit from the per-point spectra downstream (EAA's `XRF-Maps` lineage: raw scan to fitted maps). It is modelled in the detection stage of the [descriptor](../inventory.md).

## The model in one picture

The detection chain (containment, `Asset.parent_id`):

```
2-ID  (Unit, Asset)
└── FluorescenceDetector  (Device, loose Family EnergyDispersiveSpectrometer; spectrum per scan point)
        preamplifier + EPICS scalers + I0 flux monitors  (readout chain, DET-2, not separately modelled)
```

Unlike 2-BM and TomoWise, there is no scintillator, objective, or camera chain: the detector is a direct energy-dispersive device, and the per-point spectrum is the signal. This is a device class CORA's all-imaging catalog has no precedent for, which is why it binds to a loose Family string rather than a catalog Family.

## Detector

| Device | Family | Design spec / note |
| --- | --- | --- |
| `FluorescenceDetector` | `EnergyDispersiveSpectrometer` (loose) | energy-dispersive fluorescence detector; model, element channels, and segmentation unconfirmed (`DET-1`) |

The readout chain EAA names, a preamplifier (`Preamp1`), EPICS scalers, and the I0 flux monitors (ion chambers) the scan normalizes against, is the detection electronics. Their identities are unconfirmed and they are not separately modelled in this scaffold (`DET-2`).

## Families

The fluorescence detector is bound to a **loose Family string**, not a catalog Family: it is a new device class, and no Asset is registered yet to earn it. When it is earned, the catalog Family name is a naming-review decision that must avoid the reserved `Detector` Role noun (a detector is the Role an Asset plays, not its Family); `EnergyDispersiveSpectrometer` is the working placeholder. The detector model and the readout chain are the detector-side [open questions](../questions.md). See [Inventory](../inventory.md) for the Asset tree.
