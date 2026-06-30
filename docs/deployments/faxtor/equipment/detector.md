# Detector

*The indirect imaging detector: a scintillator and a fast camera. First cut; the camera model is not published, carried confirm.*

FAXTOR images indirectly: a scintillator converts the transmitted X-rays to visible light, which is relayed to a fast camera. The beamline images at 0.5-10 um pixel size with absorption, propagation-phase, and grating-based contrast. This is a reverse-engineered first cut; the detector model is not published, carried fully pending (`DET-1`).

## The detection chain

- **`Scintillator`** (`Scintillator`): the X-ray-to-visible screen; material and thickness pending (`DET-1`).
- **`Camera`** (`Camera`): the fast imaging camera that records the projections, supporting continuous-rotation tomography up to 20 Hz; sensor, frame rate, and vendor model not published, carried pending (`DET-1`).

Both bind imaging Families the fleet already carries: a `Scintillator` and a `Camera`, the same indirect-detection anatomy as the 2-BM pilot and the MAX IV TomoWISE design. FAXTOR coins no new Family.

## Named, not bound

The fast camera is the decision-critical device whose model FAXTOR's public sources do not give: the brief found the detector unpublished, so a `Camera` Asset is carried fully pending rather than guessed (`DET-1`). It is named here so the detection chain is real in the model, with its sensor, frame rate, and model left to ALBA staff to confirm. Whether FAXTOR carries interchangeable microscopes or a fixed magnification, and the relay optics, are part of the same open question. The [2-BM microscope](../../2-bm/equipment/microscope.md) shows the shape a fully-modelled imaging detector carries.
