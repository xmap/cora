# Techniques

*What CORA would run at FMX: macromolecular crystallography, each a [Catalog](../../catalog/methods.md) Method. FMX is CORA's second MX beamline (after Diamond i03) and follows the same Method-deferral discipline.*

FMX's science is protein crystallography: rotate a cryo-cooled crystal in a focused microbeam and read the diffraction on the Eiger, locate crystals with fast grid scans, and exchange samples with a robot. These are the MX Methods i03 brought to CORA; FMX is their second consumer. The Methods below render unlinked and stay pending until the owner-scope decision (TECH-1) brings them into the catalog.

| Technique | Beam | Detector | Status in CORA |
| --- | --- | --- | --- |
| Rotation (oscillation) data collection | monochromatic, microfocused | `AreaDetector` (Eiger, Detector Role) | the i03 `mx_data_collection` Method binding Goniometer + Eiger + vector + Zebra, pending; 2nd consumer (TECH-1) |
| Grid scan / sample location | monochromatic, microfocused | `AreaDetector` + `SampleCamera` | the i03 `grid_scan` Method over the Zebra-triggered goniometer raster, pending; 2nd consumer (TECH-1) |
| Autonomous sample exchange | n/a | n/a | the i03 `sample_exchange` Method: a Procedure over the spine + a Subject custody thread, pending; 2nd consumer (ROBOT-1) |
| Anomalous element ID (fluorescence) | monochromatic, energy-swept | `FluorescenceDetector` (Mercury, Sensor) | the edge scan picks the energy for SAD / MAD; reuses the energy axis (DET-1) |
| Fixed-target serial (chip) | monochromatic, microfocused | `AreaDetector` | the chip-scanner raster; reuses the `serial_crystallography` Method (i24 / LCLS-MFX), deferred (SERIAL-1) |

## Why the Methods stay pending

FMX reuses the three MX Methods Diamond i03 left pending. Unlike a loose device *Family* (which a second sighting promotes on a mechanical rule-of-three, as ISS did for the emission spectrometer), a pending *Method* has no automatic promotion: it is coined by deliberate decision when a conduct-path needs it, the same discipline that keeps `energy_scan` deferred even across several consumers. FMX makes each of `mx_data_collection`, `grid_scan`, and `sample_exchange` a two-consumer Method (i03 + FMX), which strengthens the eventual case to coin them but does not force it in a descriptor scaffold (TECH-1). The device Roles already exist (the graduated `Goniometer` presents Positioner, the Eiger presents Detector), so what is pending is the recipe, not a device shape.

The autonomous sample-exchange loop is the genuinely non-obvious modelling: the unattended sequence (load pin, centre, collect, unmount, next) is a Procedure over the spine, threaded through the `Subject` custody lifecycle (Received to mounted to measured to Returned) and gated by a Clearance issued after a safety review. The robot itself is just a Positioner Asset; the workflow is the modelling (ROBOT-1). The per-experiment recipes (oscillation ranges, exposure, grid parameters, the exchange sequence) are calibration the deployment must supply.
