# Governance

*Who would act at i06, and the trust shape that would gate it. Scaffold.*

Governance at i06 follows the same model as the other Diamond beamlines: people and autonomous agents are facility principals at the [Diamond Site](../diamond/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

i06 is a further beamline at the Diamond Site, so it reuses the Diamond facility envelope rather than creating a new one: the operator pool, the safety review structure, and the safety forms are facility-wide and inherited, shared with the soft X-ray and MX siblings (I22, I03, I15-1, I11, I24). i06 adds only its own beamline-bound principals. The Diamond operator pool and review structure are site-level and shared across the beamlines, so they are not yet instantiated per beamline; they are carried pending on the [Diamond Site page](../diamond/index.md#who-acts-here) (GOV-1). None of this is in dodal, which is a controls library, not an organizational record.

Because i06 is a reverse-engineered scaffold rather than a pilot, the concrete trust shape is not instantiated. What is already settled is the boundary, the same as for every deployment: clearances (the safety forms that must be active to start) are issued at the Diamond Site, not on the beamline, and the beamline links up to them rather than restating them. The Diamond personnel safety system (PSS) clearance is carried pending because its form names are not confirmed.

## The Enclosures i06 gates

The beamline spans three enclosures, the grouping CORA's Zone would follow (ENC-1):

| Enclosure | PV zone | What it holds |
| --- | --- | --- |
| i06-optics | BL06I (optics spine), SR06I (the APPLE-II servo crates) | the PGM, the twin APPLE-II controllers, and the i06-branch PEEM sample stage |
| i06-1 | BL06J | the diffraction-dichroism endstation |
| i06-2 | BL06K | the PEEM endstation |

How the two endstations share the source, and whether the three PV zones are three separate hutches, is the beamline team's to confirm (ENC-1). The Zone grouping is named here, not built.

## The safety tier behind the beam

The safety tier behind the beam is the personnel safety system. On a soft X-ray beamline the leaves that must be satisfied before the beam can enter an enclosure are the PSS search-and-secure permit signals, and the photon and front-end shutters are what those leaves gate. Both the permit signals and the shutters are absent from dodal, so CORA does not name them and does not invent them: the Enclosure permit signals and the shutters are carried pending (PSS-1). When staff confirm the signal and shutter handles, they bind to the Enclosure as the permit leaves the way the Diamond siblings carry theirs. No interlock, PSS, or equipment-protection tier is invented in the meantime.

The hazard classes i06 brings to that envelope are those of a soft X-ray UHV beamline:

- **An intense, variable-polarization beam.** i06 is the fleet's first APPLE-II source, so the beam's polarization is a driven experiment axis (LH / LV / PC / NC / LA plus third-harmonic variants over 70-2200 eV), not a fixed property. The radiation hazard is the standard photon-shutter concern the PSS gates (PSS-1); the polarization axis adds optics state, not a new safety tier.
- **Ultra-high vacuum on the optics and both endstations.** The soft X-ray optics and the two endstations run under UHV (SUP-1). The hazard is the vacuum envelope itself, the same class the PEEM and diffraction-dichroism endstations carry.
- **In-situ temperature environments.** The i06-1 endstation carries two Lakeshore 336 controllers for sample cooling and heating (TEMP-1). The sample environment spans a temperature range whose limits are pending; the hazard is the cryogen and heater envelope at the sample.

Where these become Clearance-gated operation (for example any unattended or hazardous run) is the shape the Diamond siblings reserve, not instantiated here.

## What is deliberately not modelled

- **The PSS permit signals and shutters (PSS-1).** Absent from dodal, carried pending, not invented.
- **The Diamond operator pool and review structure (GOV-1).** Site-level and shared across the beamlines, carried pending on the Diamond Site, not instantiated per beamline.
- **The concrete Zone, Conduit, and Policy instances.** Named as the trust shape, not built; they would land if and when the beamline approaches real scope, following the [2-BM governance](../2-bm/governance.md) shape.

The deferred detectors (the i06-1 scattering detector and the PEEM electron-image column, DET-1 and PEEM-1) are equipment, not governance, decisions; they live on [Model](model.md#deliberately-not-here-yet). The full delete-on-answer queue is on [Open questions](questions.md).
