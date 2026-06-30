# Fleet recurrence: NSLS-II

Cross-fleet device-class frequency across the beamlines surveyed under `research/nsls2/beamlines/`. The point of this report is the **catalog Family graduation signal**: a device class that recurs across two or more *physically distinct* beamlines is a graduation candidate (rule-of-three is the firm trigger; two is a watch). `graduated` marks classes already in `catalog/catalog.yaml`.

Hand-compiled from the per-beamline `facts.md` device tables (the "Suggested family" column, deduplicated within each beamline). **Covers all 24 NSLS-II beamlines:** amx, bmm, cdi, chx, cms, csx, esm, fmx, fxi, hex, hxn, ios, isr, iss, ixs, lix, pdf, six, smi, srx, sst, xfm, xfp, xpd. Every PV in every pass was verified verbatim against the beamline's public controls source.

!!! warning "Count physical beamlines, not repos"
    Counts are distinct physical beamlines. ESM (arpes+xpeem) and SST (rsoxs+nexafs+haxpes+vppem) are multi-branch but each counts once.

## Suggested families by beamline count

| Family | Beamlines | Status |
| --- | --- | --- |
| GenericProbe | 23 | graduated |
| Mirror | 20 | graduated |
| LinearStage | 19 | graduated |
| Slit | 17 | graduated |
| Shutter | 17 | graduated |
| Monochromator | 17 | graduated |
| FluxMonitor | 16 | graduated |
| Camera | 14 | graduated |
| Filter | 13 | graduated |
| EnergyDispersiveSpectrometer | 11 | graduated |
| TemperatureController | 9 | graduated |
| TimingController | 7 | graduated |
| BeamStop | 7 | graduated |
| Diffractometer | 6 | LOOSE -- GRADUATION WATCH (contested contract, see below) |
| Table | 4 | graduated |
| Screen | 4 | LOOSE -- GRADUATION CANDIDATE (rule-of-three met, see below) |
| MotionController | 4 | graduated |
| GratingMonochromator | 4 | graduated |
| FlowController | 4 | graduated |
| Transfocator | 3 | graduated |
| ElectronAnalyzer | 3 | graduated |
| SpectrometerArm | 2 | LOOSE -- WATCH (see below) |
| RotaryStage | 2 | graduated |
| Manipulator | 2 | graduated |
| InsertionDevice | 2 | graduated |
| Goniometer | 2 | graduated |
| Collimator | 2 | graduated |
| Aperture / Condenser / PhaseRing / PseudoAxis / Scintillator / ZonePlate | 1 each | graduated |
| EmissionSpectrometer | 1 (iss) | graduated |
| EnergyAnalyzer | 1 (ixs) | LOOSE |
| Housing | 1 (hex) | graduated |
| BetrandLens / Microscope / Positioner | 1 each | LOOSE (single-use) |

## Graduation shortlist (the actionable output)

The full 24-beamline fleet overwhelmingly **reuses** graduated catalog Families. Three loose families now carry real signal, and one is a genuine new graduation candidate:

| Candidate / family | Distinct beamlines | Discriminator | Verdict |
| --- | --- | --- | --- |
| Screen | 4 (bmm, cdi, hxn, sst) | fluorescent / YAG diagnostic screen viewed by a camera | **GRADUATION CANDIDATE, rule-of-three met.** This signal only emerged at full-fleet scale (n=2 at 11 beamlines). A diagnostic screen is a distinct, recurring anatomy (not a Camera, not a Slit). Gate-review + naming-r3 to graduate Screen into the catalog. The cleanest new-family signal the NSLS-II fleet produced. |
| Diffractometer | 6 (chx, csx, hex, hxn, isr, xpd) | sample/detector rotation presented as a diffractometer | **WATCH, do NOT graduate yet, contested contract.** The six range from 2-axis detector-arm stubs (isr Dif:ISD = th/zeta; chx Dif = xh/zh) to a genuine multi-circle instrument (csx TARDIS). They are not one contract. RESOLVE first: graduate only the true multi-circle diffractometers; fold the 2-axis stubs to RotaryStage/LinearStage. Gate-review item. |
| SpectrometerArm | 2 (ixs, six) | grazing-incidence / arm-mounted spectrometer | **WATCH, approaching rule-of-three.** SIX (soft RIXS arm) + IXS (hard-IXS spectrometer arm). One more arm-spectrometer consumer triggers graduation. Clarify the relationship to EmissionSpectrometer (iss crystal XES) and EnergyAnalyzer (ixs crystal analyzer) at that point: three "analyze the scattered/emitted beam" families that may consolidate. |
| ElectronAnalyzer | 3 (esm, ios, sst) | hemispherical photoelectron analyzer | ALREADY graduated; full fleet confirms it cleanly (ARPES at esm, AP-XPS at ios, HAXPES at sst). No action. |
| TemperatureController | 9 | settable-setpoint thermal actuator | ALREADY graduated; the most reinforced family (pdf/xpd multi-mechanism). No action. |
| FlowController | 4 (chx, lix, xfp, xpd) | flow actuator (syringe/HPLC pumps) | ALREADY graduated; NSLS-II adds 4 consumers to the cross-facility set. No action. |

**Net over all 24:** one genuine new graduation candidate (**Screen**, rule-of-three cleanly met), one contested watch (**Diffractometer**, resolve the contract before graduating), one approaching watch (**SpectrometerArm**, n=2). Everything else is reuse or reinforcement of already-graduated families. The fleet stressed the existing vocabulary across the full technique span (MX, scattering, spectroscopy, imaging, photoemission, footprinting, RIXS, IXS) and it held, earning exactly one new family.

## Recurring loose-family / DIAG notes

- **GenericProbe (23/24)** absorbs the fleet-wide unresolved sensors: BPMs, scalers, current preamps (SR570/Keithley), electrometers, gas analyzers, viewing cameras, gate valves. This is the `DIAG-1` cluster, held by design pending the cross-facility DIAG abstraction review; do not graduate piecemeal.
- **EnergyAnalyzer (ixs) / EmissionSpectrometer (iss) / SpectrometerArm (six+ixs)** are three loose/graduated "analyze the outgoing beam" families. When SpectrometerArm hits rule-of-three, review all three together for possible consolidation vs deliberate distinction (electron vs photon, crystal vs grating, dispersive vs scanning).
- **BetrandLens / Microscope / Positioner** are single-use loose bindings; no signal.

## Provenance

Compiled from the device tables of all 24 passes (every PV verified verbatim against each `NSLS2/<bl>-profile-collection` at pass time; thin-source beamlines csx/xfm and the partial-scaffold isr flagged COVERAGE-1 in their facts). Method: per-beamline distinct "Suggested family" values, `(?)` suffixes stripped, counted across beamlines. This supersedes the 11-beamline interim report. The **Screen** graduation candidate and the **SpectrometerArm** n=2 watch are the two signals that only became visible at full-fleet scale.
