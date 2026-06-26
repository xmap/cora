# Techniques

*What CORA would run at XFM: scanning X-ray fluorescence microscopy, a [Catalog](../../catalog/methods.md) Method bound through an NSLS-II [Practice](../nsls2/index.md). XFM is the second scanning-XRF beamline (after 2-ID) and follows the same Method-deferral discipline.*

XFM's science is element mapping: raster the sample through a focused beam and read the fluorescence spectrum at each point, in a step grid or a Maia continuous fly-scan. The Method below renders unlinked and stays pending until the owner-scope decision (METHOD-1) brings it into the catalog.

| Technique | Mode | Detector | Status in CORA |
| --- | --- | --- | --- |
| Scanning XRF mapping | raster (step grid or Maia fly) | `EnergyDispersiveSpectrometer` (Xspress3 / Maia) | the 2-ID `scanning_fluorescence_microscopy` Method, pending; XFM is the 2nd consumer (METHOD-1) |
| XANES microspectroscopy | energy sweep over the `EnergyAxis` | `EnergyDispersiveSpectrometer` | the BMM energy-scan question; `energy_scan` deferred (ENERGY-1), no practice |
| XRF-tomography | raster x rotation | `EnergyDispersiveSpectrometer` | out of scope: no rotation axis in the profile (TECH-1) |

## Why the Method stays pending

XFM reuses the `scanning_fluorescence_microscopy` Method that 2-ID left pending. Unlike a loose device *Family* (which a second sighting promotes on a mechanical rule-of-three), a pending *Method* has no automatic promotion: it is coined by deliberate decision when a conduct-path needs it, the same discipline that keeps `energy_scan` deferred even across several consumers. XFM makes `scanning_fluorescence_microscopy` a two-consumer Method (2-ID + XFM), which strengthens the eventual case to coin it but does not force it in a descriptor scaffold (METHOD-1). The device Roles already exist (the SDD presents the energy-dispersive Sensor, the raster stage presents Positioner), so what is pending is the recipe, not a device shape.

The XANES microspectroscopy leg sweeps the monochromator energy across an absorption edge, which leans on the deferred `energy_scan` Capability (the BMM ENERGY-1 question); no XANES practice is recorded until that Capability lands, the SRX / BMM discipline. The XRF fitting and any tomographic reconstruction are `ComputePort` work, not beamline Methods.
