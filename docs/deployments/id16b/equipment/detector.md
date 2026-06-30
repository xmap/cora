# Detector

*The detection side. ESRF runs BLISS / Tango; the handles are the real MOSCA / Lima Tango device names read from the [public ID16B config](https://gitlab.esrf.fr/id16b/beamline_configuration), carried `confirm` (CTRL-1).*

ID16B has two detection chains, one per mode. Nano-XRF mapping reads an energy-dispersive fluorescence spectrum per raster point; nano-tomography records a projection radiograph per rotation angle. So the detection side has the fluorescence detectors, an optical spectrometer, and the area detectors, plus the stage that positions them.

| Asset | Family | Handle | Role |
| --- | --- | --- | --- |
| `FluoDetector` | [EnergyDispersiveSpectrometer](../../../catalog/families.md) | FalconX `id16b/moscav1/fxb`, `fx8` | multi-element silicon-drift XRF detector (DET-1) |
| `OpticalSpectrometer` | [EnergyDispersiveSpectrometer](../../../catalog/families.md) | QEPro `id16b/moscav1/qepro`, Hamamatsu `hama1` | optical-emission / xeol spectrometer (DET-2) |
| `TomoDetector` | [Camera](../../../catalog/families.md) | PCO `id16na/limaccds/pco1`/`pco2`, Zyla `id16b/limaccds/zyla` | indirect-detection area detector for nano-tomography (DET-1) |
| `DetectorStage` | [LinearStage](../../../catalog/families.md) | `DETPOS` | detector positioning / propagation distance (DET-1) |

## The fluorescence detector: the FalconX

The `FluoDetector` is a multi-element silicon-drift fluorescence detector read by a FalconX (a MOSCA Tango device, `id16b/moscav1/fxb`, plus a direct `fx8` over TCP). As the sample is rastered through the nanoprobe, it reads an energy-dispersive spectrum per point, and the element maps are fit downstream. CORA binds it to the catalog `EnergyDispersiveSpectrometer` family, which presents the Sensor Role: a per-point energy spectrum, not a 2D Frame. This is the same binding the NSLS-II XFM Xspress3 and the 2-ID / SRX scanning-XRF detectors use (DET-1). It is the primary nano-XRF mapping detector.

## The optical spectrometer

The `OpticalSpectrometer` is an optical-emission spectrometer (QEPro OceanOptics and a Hamamatsu, both MOSCA Tango devices) used for xeol (X-ray excited optical luminescence) or optical readout. It also reuses `EnergyDispersiveSpectrometer` (a per-point spectrum Sensor). Its exact role is DET-2.

## The science detector: the area cameras

The `TomoDetector` is the indirect-detection area detector for nano-tomography: a scintillator converts the X-ray projection to visible light, optics relay it, and a camera records the frame. ID16B fields PCO cameras (`pco1`, `pco2`) and an Andor Zyla, all Lima Tango device servers. CORA binds them to the catalog `Camera` family, which presents the Detector Role (DET-1). The `DetectorStage` (`DETPOS`) positions the detector and sets the propagation distance for phase contrast.

## Why no new family for the detectors

ID16B's detectors are exactly what the catalog already covers: the XRF detector is an `EnergyDispersiveSpectrometer` (the established scanning-XRF binding), the area detectors are `Camera`s. CORA coins no new family; nothing graduates. The techniques are the existing [`tomography`](../../../catalog/methods.md) and pending `scanning_fluorescence_microscopy` Methods (TECH-1, METHOD-1), and the reconstructions (the tomographic volume, the XRF map fitting) are `ComputePort` work, not beamline devices. The catalog is unchanged.

The novelty at ID16B is the control floor and the nanoprobe combination, not the detectors: ESRF runs BLISS / Tango, so these detectors are MOSCA and Lima Tango device servers rather than EPICS areaDetectors (CTRL-1, see [Controls](controls.md)).

## What is deferred

The sample environments (cryostream, furnace, xeol) and their regulation are noted, not modelled in this cut (ENV-1). The PSS permit signals behind the shutters are not in the config and carried pending (PSS-1). See [the beam path](../beamline.md) for the generated source-walk.
