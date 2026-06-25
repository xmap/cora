# Detector

*Detection at both i10 endstations is point, current-integrating, and modelled. Unlike i06, whose recording detectors were absent from dodal, i10's detection IS present: the channels read through current amplifiers, so this page binds them now. PVs read from dodal, carried confirm.*

i10 has two endstations and one detection shape: read the beam as a current, not as an image. RASOR scatters and reflects soft X-rays and reads the scattered-beam point detector plus the incident-flux, fluorescence, and drain-current channels through current amplifiers; i10-1 measures dichroism in an applied field and reads the total-electron-yield, fluorescence, diode, and monitor channels. No area detector exists at either station. So the science detector at each endstation binds the catalog `FluxMonitor` Family rather than a camera or an area-detector Family, and that is an honest description of the hardware, not a placeholder. The geometry around the detector, the RASOR two-theta scattering arm and the reciprocal-space axis, rides the diffractometer on the sample side and is modelled there. The detection channels live in the detection stage of the [descriptor](../inventory.md).

## RASOR point detection (ME01D)

The RASOR endstation is a soft X-ray diffractometer and reflectometer. The signal it records is the current from a point detector in the scattering plane, normalized against the incident flux, with fluorescence and drain-current channels read alongside. dodal exposes these as scaler channels through `Femto` / `SR570` current amplifiers; the scaler is a `Struck` counting unit. CORA binds the set as one science `Detector` on the catalog `FluxMonitor` Family (DET-1).

| Device | Family | Role | Channel | Notes |
| --- | --- | --- | --- | --- |
| `Detector` | `FluxMonitor` | Sensor | scaler `S18` | scattered-beam point detector; the RASOR scattering / reflectivity signal (DET-1) |
| `Detector` (I0) | `FluxMonitor` | Sensor | scaler `S17` | incident-flux monitor the signal is normalized against (DET-1) |
| `Detector` (FY) | `FluxMonitor` | Sensor | scaler `S19` | fluorescence channel (DET-1) |
| `Detector` (TEY) | `FluxMonitor` | Sensor | scaler `S20` | drain-current / total-electron-yield channel (DET-1) |
| `Diffractometer` (two-theta arm) | `Goniometer` | Positioner | `ME01D-MO-DIFF-01` | the two-theta scattering arm that places the point detector; part of the sample-side goniometer (DIFF-1) |
| `ReciprocalSpace` | `PseudoAxis` | Axis | over the RASOR circles | reciprocal-space axis driving the circles to a reflection; sits over the diffractometer, not the detector (DIFF-2) |
| `DetectorSlit` | `Slit` | Positioner | `ME01D-MO-APTR-0` | detector-side baffle slit (STAGE-1) |

How this maps onto CORA:

- **The four channels are one `FluxMonitor` Detector, read through current amplifiers.** S18 is the scattered-beam point detector, S17 the incident-flux monitor, S19 fluorescence, and S20 the drain-current / total-electron-yield channel, all integrated currents through `Femto` / `SR570` amplifiers onto a `Struck` scaler. They are the same device kind as the `FluxMonitor` Family; which channel is the primary signal versus an auxiliary monitor is a Method concern, not a Family difference. The per-channel binding and amplifier gain are the open detail (DET-1).
- **The two-theta arm is goniometer geometry, not a detector.** The RASOR scattering arm that carries the point detector is part of the `Goniometer` the diffractometer binds (DIFF-1); it places the detector in the scattering plane. CORA models that arm as the goniometer affordance it is on the [sample](sample.md) side, and the `FluxMonitor` Detector is the separate Asset that the arm carries.
- **The reciprocal-space axis is over the circles, not the detector.** `ReciprocalSpace` reuses `PseudoAxis` and drives the diffractometer circles to a reflection (DIFF-2). It is a sibling of the incident-energy and polarization pseudo-axes; it tells the mechanics where to point and does not stand in for the detector.
- **The analyzer arm is sample-side, and its crystal is implicit.** RASOR's polarization-analysis arm (the PaStage / POLAN arm, `ME01D-MO-POLAN-01`) carries its own analyzer two-theta and detector. It binds the loose `PolarizationAnalyzer` Family, held under review (POL-2), and is modelled with the rest of the analyzer mechanics on the [sample](sample.md) side; dodal exposes the arm motors only, so no analyzer-crystal specifics are invented here.

## i10-1 / I10J point detection (BL10J)

The i10-1 endstation measures X-ray magnetic dichroism with the sample in an applied magnetic field at low temperature. Its detection is again point and current-integrating: the absorption is read as total-electron-yield, fluorescence, diode, and monitor channels. No area detector is present. CORA binds the set as one science `MagnetDetector` on the catalog `FluxMonitor` Family (DET-1).

| Device | Family | Role | Note |
| --- | --- | --- | --- |
| `MagnetDetector` (TEY) | `FluxMonitor` | Sensor | drain-current / total-electron-yield channel (DET-1) |
| `MagnetDetector` (FY) | `FluxMonitor` | Sensor | fluorescence channel (DET-1) |
| `MagnetDetector` (diode) | `FluxMonitor` | Sensor | diode channel (DET-1) |
| `MagnetDetector` (monitor) | `FluxMonitor` | Sensor | incident / reference monitor channel (DET-1) |

How this maps onto CORA:

- **The dichroism channels are one `FluxMonitor` Detector.** The TEY, FY, diode, and monitor channels are the i10-1 point detection; they reuse `FluxMonitor`, the same Family the RASOR channels bind. The channel map and amplifier bindings are the open detail (DET-1). There is no area detector at i10-1, so nothing else is coined.
- **The dichroism / resonant signal is read against the polarization axis on the source side.** An XMCD or XMLD difference subtracts signal taken at one polarization from signal taken at another. The channels above produce that signal; the axis they are differenced against is the `Polarization` pseudo-axis over the twin APPLE-II phase rows, modelled on the source side with the value domain LH / LV / PC / NC / LA plus third-harmonic variants, the continuous linear-arbitrary-angle being the realization of the LA value within the same axis (POL-1). See the [Beamline source walk](../beamline.md).

## Why FluxMonitor, not a new detector Family

Both endstations bind the catalog `FluxMonitor` Family for their science detector, and that is a deliberate modelling decision, not a shortcut.

- **The detection is point and current-integrating.** Neither RASOR nor i10-1 records an image. Both read a beam as an integrated current through `Femto` / `SR570` amplifiers onto a scaler, normalized against an incident-flux channel. That is exactly what `FluxMonitor` describes, so the science detector reuses it rather than coining a synonym.
- **The BMM precedent settles the role nuance.** BMM's ion chambers are the *primary* XAS signal yet still bind `FluxMonitor`, because the role distinction (primary signal versus auxiliary monitor) is a Method concern, not a Family difference. i10 follows that precedent: a point detector that is the scattering signal and a monitor that normalizes it are the same device kind, separated by their role in a Method, not by Family.
- **No area detector exists, so none is invented (DET-1).** Coining a camera or area-detector Family for hardware that has no PV in dodal would leave an orphan in the catalog. If a future area detector appears at either endstation, the science detector migrates to the camera / area-detector Family it then earns, and the `FluxMonitor` channels stay as the flux and yield monitors they already are. Until then the catalog is unchanged by this deployment, and nothing graduates here.

## Families

No new detector Family is coined and nothing graduates. Reused from the catalog: `FluxMonitor` for the RASOR point detection (the S18 scattered-beam, S17 incident-flux, S19 fluorescence, and S20 drain-current / total-electron-yield channels) and the i10-1 TEY / FY / diode / monitor channels (DET-1); `Goniometer` for the diffractometer and its two-theta detector arm (DIFF-1); `PseudoAxis` for the reciprocal-space axis (DIFF-2); `Slit` for the detector-side slit (STAGE-1). The RASOR analyzer arm binds the loose `PolarizationAnalyzer` Family, held under review and modelled on the sample side (POL-2). See [Sample](sample.md) for the diffractometer, analyzer arm, and stage geometry, [Inventory](../inventory.md) for the full Asset tree, [Model](../model.md) for the modelling decisions, [Beamline source walk](../beamline.md) for the polarization axis the dichroism signal is read against, and the [Family catalog](../../../catalog/families.md) for the shared definitions.
