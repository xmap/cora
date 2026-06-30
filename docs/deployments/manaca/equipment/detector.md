# Detector

*The MX area detector and its stage, the on-axis viewing camera, and the flux monitor. First cut; the detector model is not published, carried confirm.*

MANACA records diffraction on an area detector reading the rotation frames as the goniometer oscillates. This is a reverse-engineered first cut; the detector model is not published, carried pending (`DET-1`).

## The detection chain

- **`AreaDetector`** (`Camera`): the MX area detector reading the rotation frames, a Pilatus / Eiger-class photon-counting detector; sensor and vendor model not published, carried pending (`DET-1`). Reuses `Camera`.
- **`DetectorStage`** (`LinearStage`): the detector translation setting the sample-to-detector distance; handles pending (`DET-1`).
- **`OnAxisCamera`** (`Camera`): the on-axis viewing camera for sample centring; reuses `Camera`; handles pending (`DET-1`).
- **`FluxMonitor`** (`FluxMonitor`): the incident-flux monitor; reuses the graduated `FluxMonitor` family; handles pending (`DIAG-1`).

These bind the MX detection Families the fleet already carries (i03 / FMX / AMX / MX3): an area-detector `Camera`, a detector `LinearStage`, an on-axis `Camera`, and a `FluxMonitor`. MANACA coins no new Family.

## Named, not bound

The area detector is the decision-critical device whose model MANACA's public sources do not give: the brief found the detector unpublished, so a `Camera` Asset is carried pending rather than guessed (`DET-1`). It is named here so the detection chain is real in the model, with its sensor, frame rate, and model left to LNLS staff to confirm. The [i03 detector](../../i03/equipment/detector.md) page shows the shape a fully-modelled MX detector carries.
