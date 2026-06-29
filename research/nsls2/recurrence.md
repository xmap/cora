# Fleet recurrence: NSLS-II

Cross-fleet device-class frequency across the beamlines surveyed under `research/nsls2/beamlines/`. The point of this report is the **catalog Family graduation signal**: a device class that recurs across two or more *physically distinct* beamlines is a graduation candidate (rule-of-three is the firm trigger; two is a watch). `graduated` marks classes already in `catalog/catalog.yaml`.

Hand-compiled from the per-beamline `facts.md` device tables (the "Suggested family" column, deduplicated within each beamline). Covers the **11 beamlines surveyed so far**: bmm, srx, iss, chx, fxi, pdf, hxn, cms, xpd, ios, fmx. The remaining 13 NSLS-II beamlines (amx, cdi, csx, esm, hex, isr, ixs, lix, six, smi, sst, xfm) are not yet device-passed; re-run this report when they land.

!!! warning "Count physical beamlines, not repos"
    Counts here are distinct physical beamlines. ESM and SST (multi-branch, not yet passed) will each count once when added, not once per branch.

## Suggested families by beamline count

| Family | Beamlines | Status |
| --- | --- | --- |
| Shutter | 11 | graduated |
| Mirror | 11 | graduated |
| GenericProbe | 11 | graduated |
| Slit | 10 | graduated |
| Monochromator | 10 | graduated |
| LinearStage | 10 | graduated |
| FluxMonitor | 9 | graduated |
| Camera | 9 | graduated |
| Filter | 8 | graduated |
| EnergyDispersiveSpectrometer | 7 | graduated |
| TemperatureController | 5 | graduated |
| TimingController | 4 | graduated |
| BeamStop | 4 | graduated |
| MotionController | 3 | graduated |
| Diffractometer | 3 | LOOSE -- GRADUATION WATCH (see below) |
| Transfocator | 2 | graduated |
| Table | 2 | graduated |
| RotaryStage | 2 | graduated |
| FlowController | 2 | graduated |
| Screen | 2 | LOOSE |
| Aperture | 1 | graduated |
| Collimator | 1 | graduated |
| Condenser | 1 | graduated |
| ElectronAnalyzer | 1 | graduated |
| EmissionSpectrometer | 1 | graduated |
| Goniometer | 1 | graduated |
| GratingMonochromator | 1 | graduated |
| InsertionDevice | 1 | graduated |
| PhaseRing | 1 | graduated |
| PseudoAxis | 1 | graduated |
| Scintillator | 1 | graduated |
| ZonePlate | 1 | graduated |
| Positioner | 1 | graduated (role-as-family fallback; SampleChanger folds here) |
| Microscope | 1 | LOOSE (srx VLM; likely Camera+stage, not the X-ray Microscope family) |
| BetrandLens | 1 | LOOSE (fxi; source spelling; single use) |

## Graduation shortlist (the actionable output)

Almost every recurring class is already a graduated catalog Family: the NSLS-II fleet overwhelmingly **reuses** existing vocabulary rather than demanding new. The genuine signals:

| Candidate / family | Distinct beamlines | Discriminator | Blocker / note |
| --- | --- | --- | --- |
| Diffractometer | 3 (chx, hxn, xpd) | a sample/detector rotation stage presented as a diffractometer | LOOSE and rule-of-three is MET, BUT each facts.md flagged "confirm Diffractometer vs a plain rotation/linear stage" -- the three may not be the same contract (chx Dif = xh/zh 2-axis; xpd Dif:1/Dif:2; hxn Diff). RESOLVE the contract before graduating: if they are genuine multi-circle diffractometers, graduate; if they are detector-arm stages, fold to RotaryStage/LinearStage. Gate-review + naming-r3. |
| TemperatureController | 5 (chx, cms, fxi, pdf, xpd) | settable-setpoint thermal actuator (presents Regulator) | ALREADY graduated. NSLS-II massively reinforces it: pdf + xpd each bind 3+ distinct mechanisms (Lakeshore, Linkam, Eurotherm, CS800, Env). No action; strongest confirmation in the fleet. |
| FlowController | 2 (chx, xpd) | flow actuator (syringe pumps; presents Regulator) | ALREADY graduated. chx + xpd syringe pumps add to the cross-facility consumers (Diamond memo: i22/7-bm/lix/xfp). Reinforces, no action. |
| TimingController | 4 (chx, fmx, fxi, srx) | fly-scan pulse/gate generator (Zebra) | ALREADY graduated. Every Zebra was tagged `(?)` "confirm timing role" in the passes -- a cross-fleet confirmation task, not a graduation: verify the Zebra binds TimingController vs a bare probe. |
| EmissionSpectrometer | 1 here (iss: Johann + von Hamos) | crystal emission spectrometer (XES/HERFD) | ALREADY graduated. ISS gives it 2 device consumers on ONE beamline; clarify vs the loose SpectrometerArm (RIXS arm) when a 2nd RIXS lands. |

**Net:** no new Family is earned by the 11-beamline NSLS-II pass. The one open graduation-shaped question is **Diffractometer** (loose, n=3 but contested contract) -- a gate-review item, NOT to be coined from a deployment scaffold. Everything else is reuse or reinforcement of already-graduated families, which is the intended outcome: the fleet stresses the existing vocabulary and it holds.

## Recurring loose-family / DIAG notes

- **GenericProbe (11/11)** absorbs the fleet-wide unresolved sensors: BPMs, scalers, current preamps, electrometers, gas analyzers, viewing cameras. This is the `DIAG-1` cluster (beam-position fragmentation across BeamPositionMonitor / Diagnostic / GenericProbe) plus scalers/preamps. Held by design pending the cross-facility DIAG abstraction review; do not graduate piecemeal.
- **Microscope / BetrandLens / Screen** are single-use loose bindings; no signal.

## Provenance

Compiled from the device tables of the 11 passes listed above (all PVs verified verbatim against each `NSLS2/<bl>-profile-collection` at pass time). Method: per-beamline distinct "Suggested family" values, `(?)` suffixes stripped, counted across beamlines. Re-generate when the remaining 13 beamlines are passed; the Diffractometer count in particular may shift (e.g. ixs, six diffractometers).
