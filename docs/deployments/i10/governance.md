# Governance

*Who would act at i10, and the trust shape that would gate it. Scaffold.*

Governance at i10 follows the same model as the other Diamond beamlines: people and autonomous agents are facility principals at the [Diamond Site](../diamond/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

i10 is a further beamline at the Diamond Site, so it reuses the Diamond facility envelope rather than creating a new one: the operator pool, the safety review structure, and the safety forms are facility-wide and inherited, shared with the soft X-ray and MX siblings (I22, I03, I15-1, I11, I24, I06). i10 adds only its own beamline-bound principals. The Diamond operator pool and review structure are site-level and shared across the beamlines, so they are not yet instantiated per beamline; they are carried pending on the [Diamond Site page](../diamond/index.md#who-acts-here) (GOV-1). None of this is in dodal, which is a controls library, not an organizational record.

Because i10 is a reverse-engineered scaffold rather than a pilot, the concrete trust shape is not instantiated. What is already settled is the boundary, the same as for every deployment: clearances (the safety forms that must be active to start) are issued at the Diamond Site, not on the beamline, and the beamline links up to them rather than restating them. The Diamond personnel safety system (PSS) clearance is carried pending because its form names are not confirmed.

i10 is i06's soft X-ray twin: the two beamlines share a twin-APPLE-II and PGM spine and feed branch endstations. The governance shape is the same on both, and i10 inherits it the same way, so this page reads as the i06 page does, with the hazard classes that are particular to i10 called out below.

## The Enclosures i10 gates

The beamline spans three enclosures, the grouping CORA's Zone would follow (ENC-1):

| Enclosure | PV zone | What it holds |
| --- | --- | --- |
| i10-optics | BL10I (optics spine), SR10I (the APPLE-II servo crates) | the PGM, the twin APPLE-II controllers, and the collimating and switching mirrors |
| i10-rasor | ME01D | the RASOR resonant-scattering and reflectivity endstation, with its branch focusing mirror |
| i10-1 / I10J | BL10J | the magnet endstation, with its electromagnet and superconducting magnet |

How the two endstations share the source, and whether the three PV zones are three separate hutches, is the beamline team's to confirm (ENC-1). The Zone grouping is named here, not built.

## The safety tier behind the beam

The safety tier behind the beam is the personnel safety system. On a soft X-ray beamline the leaves that must be satisfied before the beam can enter an enclosure are the PSS search-and-secure permit signals, and the photon and front-end shutters are what those leaves gate. Both the permit signals and the shutters are absent from dodal, so CORA does not name them and does not invent them: the Enclosure permit signals and the shutters are carried pending (PSS-1). When staff confirm the signal and shutter handles, they bind to the Enclosure as the permit leaves the way the Diamond siblings carry theirs. No interlock, PSS, or equipment-protection tier is invented in the meantime.

The hazard classes i10 brings to that envelope are those of a soft X-ray UHV beamline, plus the magnet endstation's own:

- **An intense, variable-polarization beam.** i10 is the fleet's second APPLE-II source, after i06, so the beam's polarization is a driven experiment axis (LH / LV / PC / NC / LA plus third-harmonic variants, with the continuous linear-arbitrary-angle the realization of the LA value within the same axis) rather than a fixed property (POL-1). The radiation hazard is the standard photon-shutter concern the PSS gates (PSS-1); the polarization axis adds optics state, not a new safety tier.
- **Ultra-high vacuum on the optics and the endstations.** The soft X-ray optics run under UHV (SUP-1). The hazard is the vacuum envelope itself, the same class the Diamond soft X-ray siblings carry.
- **High magnetic fields at i10-1.** The i10-1 / I10J endstation carries an electromagnet (BL10J-EA-MAGC-01) and a superconducting magnet whose field can be swept (BL10J-EA-SMC-01), both modelled on the loose Magnet family (MAG-1). A superconducting magnet is a high-field environment, a class of hazard the optics and the RASOR endstation do not carry. CORA does not invent field values or sweep specifics (MAG-1); what it records is that this endstation adds a hazard class the rest of the beamline does not have.
- **Cryogenics at the sample.** The RASOR sample sits on a cryostat stage (ME01D-MO-CRYO-01) read by a Lakeshore 340 (ME01D-EA-TCTRL-01), and the i10-1 magnet endstation folds a cryostat low-temperature environment into its stages, read by a Lakeshore 336 (BL10J-EA-TCTRL-41) (TEMP-1). The hazard is the cryogen and low-temperature envelope at the sample, the same class the soft X-ray siblings carry, here paired with the magnet field at i10-1.

Where these become Clearance-gated operation (for example any unattended or hazardous run, or a superconducting-magnet field sweep) is the shape the Diamond siblings reserve, not instantiated here.

## What is deliberately not modelled

- **The PSS permit signals and shutters (PSS-1).** Absent from dodal, carried pending, not invented.
- **The Diamond operator pool and review structure (GOV-1).** Site-level and shared across the beamlines, carried pending on the Diamond Site, not instantiated per beamline.
- **The concrete Zone, Conduit, and Policy instances.** Named as the trust shape, not built; they would land if and when the beamline approaches real scope, following the [2-BM governance](../2-bm/governance.md) shape.

The hold-versus-graduate calls on the loose families (the RASOR analyzer arm on PolarizationAnalyzer, POL-2, and the magnet devices on Magnet, MAG-1) are equipment, not governance, decisions; they live on [Model](model.md). The full delete-on-answer queue is on [Open questions](questions.md).
