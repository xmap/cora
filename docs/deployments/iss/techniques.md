# Techniques

*What CORA would run at ISS: X-ray absorption and X-ray emission spectroscopy, each a [Catalog](../../catalog/methods.md) Method. ISS follows the deferral discipline of the beamlines that brought spectroscopy to CORA.*

ISS's measurement is energy spectroscopy: it sweeps the incident energy across an absorption edge (EXAFS) and, with the crystal emission spectrometers, resolves the emitted spectrum (XES) or selects an emission line during the incident-energy sweep (HERFD). The Methods below render unlinked and are carried pending until the owner-scope decision (TECH-1) brings them into the catalog.

| Technique | Mode | Notes |
| --- | --- | --- |
| X-ray absorption (EXAFS) | transmission / fluorescence, energy fly-scan | I0 / It / Ir ion chambers or the Xspress3 SDD over a trajectory energy sweep; the BMM energy-scan question (ENERGY-1, TECH-1) |
| X-ray emission (XES) | emission spectrometer, fixed incident energy | the Johann or von Hamos crystal spectrometer disperses the emitted spectrum onto the area detector (SPEC-1, TECH-1) |
| HERFD | emission spectrometer, incident-energy fly-scan | high-energy-resolution fluorescence detection: scan the incident energy, read one emission line through the analyzer (ENERGY-1, SPEC-1) |

All three need the [sample stage](equipment/sample.md) and a [detector](equipment/detector.md); the trajectory fly-scan sweeps the energy and the analog pizza box reads the detectors synchronously.

## Why the Method scope stays pending

ISS's absorption and emission both lean on energy spectroscopy CORA carries pending. EXAFS is the energy-sweep-as-the-measurement case BMM raised: the `energy_scan` Capability is anticipated in the catalog but deferred until a conduct-path forces it (ENERGY-1), and a descriptor scaffold does not force it; ISS is a further consumer that strengthens the case without coining it. The emission techniques (XES, HERFD) are the same shape LCLS-MFX left pending as the `xas_spectroscopy` Method (XAS / XES via the emission spectrometer), so ISS **reuses** that Method as the second consumer rather than coining a new one (TECH-1), and records that one pending Practice on the [NSLS-II Site](../nsls2/index.md). The device Roles already exist (the ion chambers present Sensor, the SDD the energy-dispersive Sensor, the emission spectrometers the Detector Role); what is new is the science Method, not a device shape.

The per-technique reduction (EXAFS normalization and fitting, XES / HERFD spectra) is `ComputePort` work, not beamline Methods.
