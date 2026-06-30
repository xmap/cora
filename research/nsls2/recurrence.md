# Fleet recurrence: NSLS-II

Cross-fleet device-class frequency across the beamlines surveyed under `research/nsls2/beamlines/`. The point of this report is the **catalog Family graduation signal**: a device class that recurs across two or more *physically distinct* beamlines is a graduation candidate (rule-of-three is the firm trigger; two is a watch). `graduated` marks classes already in `catalog/catalog.yaml`.

Hand-compiled from the per-beamline `facts.md` device tables (the "Suggested family" column, deduplicated within each beamline). **Covers all 28 NSLS-II beamlines with a public profile-collection:** the 24 in `deployments/nsls2/site.yaml` (amx, bmm, cdi, chx, cms, csx, esm, fmx, fxi, hex, hxn, ios, isr, iss, ixs, lix, pdf, six, smi, srx, sst, xfm, xfp, xpd) plus 4 research-only (not yet deployment-scaffolded): **qas (7-BM quick-EXAFS), tes (8-BM tender-XAS), nyx (19-ID MX), opls (12-ID-1 SAXS)**. Every PV in every pass was verified verbatim against the beamline's public controls source.

!!! warning "Count physical beamlines, not repos"
    Counts are distinct physical beamlines. ESM (arpes+xpeem) and SST (rsoxs+nexafs+haxpes+vppem) are multi-branch but each counts once. OPLS (12-ID-1) and SMI (12-ID-2) share the 12-ID straight but are distinct beamlines, counted separately.

## Suggested families by beamline count

| Family | Beamlines | Status |
| --- | --- | --- |
| GenericProbe | 27 | graduated |
| Mirror | 24 | graduated |
| LinearStage | 23 | graduated |
| Slit | 20 | graduated |
| Shutter | 20 | graduated |
| Monochromator | 20 | graduated |
| FluxMonitor | 18 | graduated |
| Camera | 17 | graduated |
| Filter | 14 | graduated |
| EnergyDispersiveSpectrometer | 13 | graduated |
| TemperatureController | 11 | graduated |
| TimingController | 8 | graduated |
| BeamStop | 8 | graduated |
| Diffractometer | 6 | LOOSE -- GRADUATION WATCH (contested contract, see below) |
| Table | 5 | graduated |
| Screen | 5 | LOOSE -- GRADUATION CANDIDATE (rule-of-three met, see below) |
| MotionController | 5 | graduated |
| FlowController | 5 | graduated |
| Transfocator | 4 | graduated |
| GratingMonochromator | 4 | graduated |
| Goniometer | 3 | graduated |
| ElectronAnalyzer | 3 | graduated |
| Collimator | 3 | graduated |
| SpectrometerArm | 2 | LOOSE -- WATCH (see below) |
| RotaryStage | 2 | graduated |
| Manipulator | 2 | graduated |
| InsertionDevice | 2 | graduated |
| Positioner | 2 | graduated (role-as-family; SampleChanger/robot folds here: nyx, pdf) |
| Aperture / Condenser / PhaseRing / PseudoAxis / Scintillator / ZonePlate | 1 each | graduated |
| EmissionSpectrometer | 1 (iss) | graduated |
| EnergyAnalyzer | 1 (ixs) | LOOSE |
| Housing | 1 (hex) | graduated |
| BetrandLens / Microscope | 1 each | LOOSE (single-use) |

## Graduation shortlist (the actionable output)

The full 28-beamline fleet overwhelmingly **reuses** graduated catalog Families. The signals:

| Candidate / family | Distinct beamlines | Discriminator | Verdict |
| --- | --- | --- | --- |
| Screen | 5 (bmm, cdi, hxn, qas, sst) | fluorescent / YAG diagnostic screen viewed by a camera | **GRADUATION CANDIDATE, rule-of-three cleanly exceeded.** A diagnostic screen is a distinct, recurring anatomy (not a Camera, not a Slit). The one genuine new-family signal the fleet produced; strengthened by the 4 added beamlines (qas). Gate-review + naming-r3 to graduate Screen into the catalog. |
| Diffractometer | 6 (chx, csx, hex, hxn, isr, xpd) | sample/detector rotation presented as a diffractometer | **WATCH, do NOT graduate yet, contested contract.** Range from 2-axis detector-arm stubs (isr, chx) to a genuine multi-circle instrument (csx TARDIS). Not one contract. Resolve first: graduate only the true multi-circle ones; fold the stubs to RotaryStage/LinearStage. Gate-review item. |
| SpectrometerArm | 2 (ixs, six) | arm-mounted scattered/emitted-beam spectrometer | **WATCH, approaching rule-of-three.** Review together with EmissionSpectrometer (iss) and EnergyAnalyzer (ixs) when a 3rd consumer lands: three "analyze the outgoing beam" families that may consolidate or stay deliberately distinct. |
| Collimator | 3 (amx, fmx, nyx) | beam-defining collimator on MX endstations | ALREADY graduated; the three MX beamlines confirm it cleanly. No action (nyx pushed it to n=3). |
| Goniometer | 3 (amx, fmx, nyx) | MX sample-orientation goniometer | ALREADY graduated (i03); the NSLS-II MX trio (amx/fmx/nyx) are all consumers. No action. |
| Transfocator | 4 (chx, hxn, opls, smi) | CRL focusing optic | ALREADY graduated; opls adds a 4th NSLS-II consumer. No action. |
| TemperatureController | 11 | settable-setpoint thermal actuator | ALREADY graduated; the most reinforced family (pdf/xpd multi-mechanism). No action. |
| FlowController | 5 (chx, lix, qas, xfp, xpd) | flow actuator (syringe pumps, gas MFC) | ALREADY graduated; qas adds a gas mass-flow controller, broadening the mechanism range. No action. |
| ElectronAnalyzer | 3 (esm, ios, sst) | hemispherical photoelectron analyzer | ALREADY graduated; confirmed across ARPES/AP-XPS/HAXPES. No action. |

**Net over all 28:** one genuine new graduation candidate (**Screen**, rule-of-three cleanly exceeded at n=5), one contested watch (**Diffractometer**, resolve the contract), one approaching watch (**SpectrometerArm**, n=2). Everything else is reuse or reinforcement of already-graduated families. The 4 added beamlines (qas/tes/nyx/opls) earned no new family: they reinforced Screen, Collimator, Goniometer, Transfocator, and FlowController, all already graduated.

## Recurring loose-family / DIAG notes

- **GenericProbe (27/28)** absorbs the fleet-wide unresolved sensors: BPMs, scalers, current preamps (SR570/Keithley/K428), electrometers, gas analyzers, viewing cameras, gate valves, vacuum gauges. The `DIAG-1` cluster, held by design pending the cross-facility DIAG abstraction review.
- **EnergyAnalyzer (ixs) / EmissionSpectrometer (iss) / SpectrometerArm (six+ixs)** are three loose/graduated "analyze the outgoing beam" families; review together when SpectrometerArm hits rule-of-three.
- **BetrandLens / Microscope** are single-use loose bindings; no signal.

## Coverage note

These 28 are the NSLS-II beamlines that publish a public `*-profile-collection` on the NSLS2 GitHub org and are therefore device-modellable from source. The 4 research-only ones (qas, tes, nyx, opls) have Tier-2 passes but no deployment scaffold yet (not in `site.yaml`); promote them to deployments when a modeling decision lands. Beamlines without a public profile-collection (and pure test/variant repos: tst, sxn, bmm-caps, isr-d, xfm-maia, esm/sst sub-branches already folded) are out of scope.

## Provenance

Compiled from the device tables of all 28 passes (every PV verified verbatim against each `NSLS2/<bl>-profile-collection` at pass time; thin-source beamlines csx/xfm/opls and the partial-scaffold isr flagged COVERAGE-1 in their facts). Method: per-beamline distinct "Suggested family" values, `(?)` suffixes stripped, counted across beamlines. Supersedes the 24-beamline report. The **Screen** graduation candidate is the durable headline; the 4 added beamlines reinforced existing families rather than earning new ones.
