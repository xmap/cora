# ISS

*Inner-Shell Spectroscopy at NSLS-II, beamline 8-ID: X-ray absorption (EXAFS) by a trajectory energy fly-scan, plus X-ray emission (XES) and high-energy-resolution fluorescence detection (HERFD) on two crystal emission spectrometers. This page describes how CORA would model and run ISS; the model is reverse-engineered from public configuration, not yet confirmed by ISS staff.*

| Property | Value |
| --- | --- |
| Asset | `ISS` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 8` (PV namespace `XF:08ID*`) |
| Institution | Brookhaven National Laboratory (context; not modeled as an Asset or Facility) |
| Status | Reverse-engineered from public config (design-phase scaffold) |
| Source | 8-ID in-vacuum undulator on the NSLS-II 3 GeV ring (energy driven through the HHM trajectory) |

!!! note "How CORA would land on ISS"
    These pages describe how CORA would model, govern, and conduct ISS, the thirteenth NSLS-II beamline after [FXI](../fxi/index.md), [HXN](../hxn/index.md), [BMM](../bmm/index.md), [SRX](../srx/index.md), [SIX](../six/index.md), [CHX](../chx/index.md), [CSX](../csx/index.md), [XPD](../xpd/index.md), [ESM](../esm/index.md), [SMI](../smi/index.md), [IXS](../ixs/index.md), and [SST](../sst/index.md). They are not a survey of the beamline's current software. The hardware facts (devices, EPICS PVs, axes) are read from public NSLS-II open source (the `NSLS2/iss-profile-collection` bluesky / ophyd startup files) and verified against it; undulator parameters, crystal cuts, and physical positions are not in it, so they, and every read value, are carried `confirm` until ISS staff verify them ([Open questions](questions.md)). This is a design-phase scaffold: the descriptor and these docs, with scenarios deferred.

## The defining shape: the energy sweep is the measurement

ISS is CORA's first dedicated **X-ray absorption spectroscopy** beamline, and its defining shape is the **trajectory energy fly-scan**: the high-heat-load monochromator follows a pre-computed Bragg-angle look-up table on a Delta-Tau motion controller while the ion-chamber and fluorescence detectors stream against an encoder. The energy sweep *is* the EXAFS measurement, the textbook case for the `energy_scan` Capability the catalog has anticipated since BMM (it stays deferred, ENERGY-1; ISS is a further consumer that strengthens it). Alongside absorption, ISS reads X-ray **emission**: two crystal emission spectrometers (a back-scattering Johann and a wavelength-dispersive von Hamos) measure XES and HERFD. Those spectrometers are the value to CORA: they bring the `EmissionSpectrometer` family to its second sighting (after LCLS-MFX's von Hamos), which GRADUATED it into the catalog. Every other device on ISS reuses an existing catalog Family.

## The beamline

Along the beam, in order:

- [Source](beamline.md): the 8-ID undulator, the front-end slit and shutters, then the optics, the high-heat-load trajectory monochromator and the high-resolution monochromator, the collimating and focusing mirrors, the harmonic-rejection mirror, the filter box, and the slits.
- [Sample](equipment/sample.md): the sample stage and goniometer, the energy-calibration reference foil wheel, and the thermal environment.
- [Detector](equipment/detector.md): the transmission / fluorescence ion chambers, the silicon-drift fluorescence detector, the area detector, and the Johann and von Hamos crystal emission spectrometers.

Cutting across all three:

- [Controls](equipment/controls.md): the trajectory fly-scan, the analog pizza box readout, and the motion controllers.

The cross-cutting reference view is the [Inventory](inventory.md).

## Techniques

[Techniques](techniques.md): the absorption (EXAFS) and emission (XES / HERFD) techniques ISS runs, and why their Method scope stays pending.

## Governance

[Governance](governance.md): who may act at ISS and the trust shape CORA applies; CORA brings its own per-Actor authority.

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's ISS content lives, and the `EmissionSpectrometer` graduation it earned.
