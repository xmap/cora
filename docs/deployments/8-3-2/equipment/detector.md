# Detector

*The indirect imaging detector: a scintillator, a camera objective, a camera, and the motorized detector stack. First cut; the camera model is per-dataset, carried confirm.*

8.3.2 images indirectly: a scintillator converts the transmitted X-rays to visible light, a microscope objective relays the image, and a camera records it, all carried on a motorized stack that sets the sample-to-detector distance. This is a reverse-engineered first cut; the detector structure is read from the DXchange / DXfile HDF5 data record, but the detector specs are per-dataset acquisition values, not a fixed manifest, so no vendor model is bound (`DET-1`).

## The detection chain

- **`Scintillator`** (`Scintillator`): the X-ray-to-visible screen; the data record carries `scintillator_type`. Material and thickness pending (`DET-1`).
- **`CameraObjective`** (`Objective`): the microscope objective relaying the scintillator image to the camera; the data record carries `camera_objective` (the selected magnification). The objective set is pending (`DET-1`).
- **`Camera`** (`Camera`): the imaging camera that records the projections; the data record carries `model`, `pixel_size`, `binning_x` / `binning_y`, `exposure_time`, `temperature`, `dimension_x` / `dimension_y`, `dark_field_value`, and `delay_time`. These are per-dataset values, so the vendor model is carried pending (`DET-1`).
- **`DetectorStack`** (`LinearStage`): the motorized stack setting the sample-to-detector propagation distance; the data record's `camera_motor_stack` carries `camera_distance` (the propagation distance used in phase-contrast reconstruction), `camera_elevation`, and `tilt_motor` (`DET-2`).

These bind imaging Families the fleet already carries: a `Scintillator`, an `Objective`, a `Camera`, and a `LinearStage`, the same indirect-detection anatomy as the 2-BM pilot and the NSLS-II FXI design. 8.3.2 coins no new Family.

## Specs in the data record, not the manifest

The detector parameters CORA would normally read from a device manifest (the camera model, pixel size, binning, exposure) appear in 8.3.2's DXchange / DXfile HDF5 **data record** as per-dataset acquisition values, not as a fixed configuration. So the `Camera` Asset is carried with its model pending rather than bound to a vendor catalog entry (`DET-1`): the values vary per scan, and the installed camera roster is left to 8.3.2 staff to confirm. The propagation distance (`camera_distance`) is the decision-critical detector-stack value for phase-contrast reconstruction (`DET-2`). The [2-BM microscope](../../2-bm/equipment/microscope.md) shows the shape a fully-modelled imaging detector carries.
