# Techniques

*What CORA would run at AMX: macromolecular crystallography, each a [Catalog](../../catalog/methods.md) Method. AMX is CORA's third MX beamline (after Diamond i03 and NSLS-II FMX) and follows the same Method-deferral discipline.*

AMX's science is high-throughput protein crystallography: rotate a cryo-cooled crystal in a focused microbeam and read the diffraction on the Eiger, locate crystals with fast grid scans, and exchange samples with an automated robot. These are the MX Methods i03 and FMX brought to CORA; AMX is their third consumer. The Methods below render unlinked and stay pending until a conduct-path coins them (TECH-1).

| Technique | Beam | Detector | Status in CORA |
| --- | --- | --- | --- |
| Rotation (oscillation) data collection | monochromatic, microfocused | `AreaDetector` (Eiger, Detector Role) | the `mx_data_collection` Method, pending; 3rd consumer (TECH-1) |
| Grid scan / sample location | monochromatic, microfocused | `AreaDetector` + `SampleCamera` | the `grid_scan` Method over the Zebra-triggered goniometer raster, pending; 3rd consumer (TECH-1) |
| Autonomous sample exchange | n/a | n/a | the `sample_exchange` Method: a Procedure over the spine + a Subject custody thread, pending; 3rd consumer (ROBOT-1) |
| Anomalous element ID (fluorescence) | monochromatic, energy-swept | `FluorescenceDetector` (Mercury, Sensor) | the edge scan picks the energy for SAD / MAD; reuses the energy axis (DET-1) |

## Why the Methods stay pending

AMX reuses the three MX Methods i03 and FMX left pending, and is the third consumer of each. This is the moment the consumer count is strongest, so it is worth being precise about why they still do not graduate: unlike a device *Family* (which a second sighting promotes on a mechanical rule-of-three, as ISS did for the emission spectrometer), a *Method* is coined on a **conduct-path**, when a deployment actually runs it (an integration scenario or operational pilot, the way `tomography` and `xpcs` were coined). i03, FMX, and AMX are all descriptor-only scaffolds with no conduct-path, so three consumers strengthen the case but do not coin the Methods, exactly the discipline that keeps `energy_scan` deferred across its consumers. The device Roles already exist (the graduated `Goniometer` presents Positioner, the Eiger presents Detector); what is pending is the recipe.

The genuine MX graduation, coining these Methods, is a follow-on that needs an MX conduct-path scenario (the event-sourced spine work), not another descriptor scaffold. The autonomous sample-exchange loop is the non-obvious modelling: an unattended Procedure over the spine, threaded through the `Subject` custody lifecycle and gated by a Clearance (ROBOT-1).
