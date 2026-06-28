# Detector

*The detection side. ESRF runs BLISS / Tango; the handles are the real Lima Tango device names read from the [public ID19 config](https://gitlab.esrf.fr/id19/beamline_configuration), carried `confirm` (CTRL-1).*

Microtomography reconstructs a real-space volume from the stack of projection radiographs an area detector records as the sample spins through the beam. Each endstation (MR and HR) has an area detector and a stage that sets how far it sits behind the sample, the propagation distance that turns the acquisition into phase-contrast imaging.

| Asset | Family | Handle | Role |
| --- | --- | --- | --- |
| `MR_Detector` | [Camera](../../../catalog/families.md) | Lima `id19/limaccd/frelon1`, `frelon2`, `pco4k`, `dimax_lid19det1` | MR indirect-detection area detector(s) (DET-1) |
| `MR_DetectorStage` | [LinearStage](../../../catalog/families.md) | `hdx/hdy/hdz/hdthz` | MR detector positioning / propagation distance (DET-1) |
| `HR_Detector` | [Camera](../../../catalog/families.md) | Lima `id19/limaccd/frelon1`, `pco4k`, `dimax_lid19det2`, `id19/limaccds/basler1` | HR indirect-detection area detector(s) (DET-1) |
| `HR_DetectorStage` | [LinearStage](../../../catalog/families.md) | `hrxc/hryc/hrzc` | HR detector carriage / propagation distance (DET-1) |

## The science detectors: the Lima cameras

ID19's detection is indirect: a scintillator converts the X-ray projection to visible light, visible optics relay it, and a camera records the frame. At the ESRF these are Lima detectors, addressed in BLISS as `LimaCCDs` Tango device servers (`id19/limaccd/<name>`). Several cameras are interchangeable per experiment, a real strength of the beamline:

- **Frelon** CCDs (`frelon1`, `frelon2`) for high-dynamic-range tomography.
- **PCO 4k** (`pco4k`) and **PCO Dimax** high-speed cameras (`dimax_lid19det1..3`) for fast and ultra-fast tomography.
- **Basler** cameras (`basler1`, `basler2`) for HR optical / alignment use.

`MR_Detector` and `HR_Detector` each bind the catalog `Camera` family, which presents the Detector Role: an area detector that returns frames is what `Camera` is, and the Lima cameras are thin instances of it. The operative roster per experiment is DET-1; CORA carries the handles `confirm` until bound on a live run.

## The propagation stages: phase contrast

Each station's detector rides a linear stage that sets the sample-to-detector distance. ID19's long source distance gives the beam high spatial coherence, so moving the detector back from the sample lets the projection develop propagation phase contrast before it is recorded, the edge-enhancement that makes weakly-absorbing features visible. CORA binds `MR_DetectorStage` (`hdx/hdy/hdz/hdthz`) and `HR_DetectorStage` (`hrxc/hryc/hrzc`) to the catalog `LinearStage`; the propagation distance is the operative phase-contrast control (DET-1).

## Why no new family for the detector

ID19 is a microtomography beamline, and an indirect-detection area detector is exactly what the catalog `Camera` already covers (it is the same binding the 2-BM pilot and the TomoWise cameras use). CORA does not coin a new family: the detectors are `Camera`s, the propagation stages are `LinearStage`s, and nothing graduates. The technique is the existing [`tomography` Method](../../../catalog/methods.md) (TECH-1), and the volume reconstruction from the projection stack is `ComputePort` work, not a beamline device. The catalog is unchanged.

The novelty at ID19 is the control floor, not the detector: ESRF runs BLISS / Tango, so the Lima detectors here are Tango device servers rather than EPICS areaDetectors (CTRL-1, see [Controls](controls.md)).

## What is deferred

The further endstations (MH, MED, laminography, radiography, PCO) and their detectors are noted, not modelled in this cut (ENDSTATION-1). The PSS permit signals behind the shutters are not in the config and carried pending (PSS-1). The detection side modelled here is the MR and HR endstations; see [the beam path](../beamline.md) for the generated source-walk.
