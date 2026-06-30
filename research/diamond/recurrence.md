# Fleet recurrence: Diamond Light Source

Cross-fleet device-class frequency across the beamlines surveyed under `research/diamond/beamlines/`. The point of this report is the **catalog Family graduation signal**: a device class that recurs across two or more *physically distinct* beamlines is a graduation candidate (rule-of-three is the firm trigger; two is a watch). `graduated` marks classes already in `catalog/catalog.yaml`.

Hand-compiled from the per-beamline `facts.md` device tables (the "Suggested family" column, deduplicated within each beamline). **Scope: the 14 device-passed beamlines** (i04, i05, i07, i09, i16, i21, i23, b07, b16, b18, b21, i02-1, i02-2, k11). The 10 original Diamond deployments (i22, i03, i15-1, i11, i24, i06, i10, i20-1, i19, i13-1) were built deployment-by-deployment reading `dodal` at build time and carry their device data in `deployments/<bl>/beamline.yaml`, not a Tier-2 `facts.md`; their families are reflected in the deployment descriptors. This report covers the new device-pass corpus.

!!! note "dodal source idiom + partial scaffolds"
    Every PV in every pass was verified verbatim against `DiamondLightSource/dodal` at pass time. Six of the 14 are partial / stub modules where the beamline's defining instrument is absent from public dodal (i07 surface diffractometer, i16 six-circle, i21 RIXS arm, b18 scanning DCM, i02-2 plate handling, k11 imaging+diffraction); those device sets are open questions (DIFF-1 / SPEC-1 / PLATE-1 / etc.), not invented, so the counts below reflect what dodal exposes today, not the full physical beamlines.

## Suggested families by beamline count

| Family | Beamlines | Status |
| --- | --- | --- |
| GenericProbe | 10 | graduated |
| InsertionDevice | 7 | graduated |
| TemperatureController | 6 | graduated |
| Shutter | 5 | graduated |
| Monochromator | 5 | graduated |
| Camera | 5 | graduated |
| TimingController | 4 | graduated |
| Manipulator | 4 | graduated |
| LinearStage | 4 | graduated |
| GratingMonochromator | 4 | graduated |
| Slit | 3 | graduated |
| Mirror | 3 | graduated |
| Goniometer | 3 | graduated |
| FluxMonitor | 3 | graduated |
| ElectronAnalyzer | 3 | graduated |
| Filter | 2 | graduated |
| Aperture / BeamStop / RotaryStage / Table / Transfocator | 1 each | graduated |
| FlowController | 1 (b21) | graduated |
| Positioner | 1 (i04 robot) | graduated (role-as-family; robot folds here) |
| Backlight | 1 (i04) | LOOSE (single-use) |

## Graduation shortlist (the actionable output)

The Diamond exercise was an explicit **generalization test** (off-roadmap, per the survey): does CORA's vocabulary, largely shaped by APS + NSLS-II, hold at a third major facility with a different controls library (`dodal`)? Result: **it holds cleanly. No new family is earned; every recurring class is already graduated.** The signals:

| Family | Distinct beamlines | What Diamond adds | Verdict |
| --- | --- | --- | --- |
| ElectronAnalyzer | 3 (i05, i09, b07) | confirms the family at a 2nd facility across THREE vendors: MB Scientific (i05), SPECS (i09, b07), VG Scienta (i09) | ALREADY graduated (NSLS-II esm/ios/sst). Diamond proves it generalizes across facilities AND analyser vendors. Strongest cross-facility confirmation in the project. No action. |
| Manipulator | 4 (i05, i09, i21, b07) | photoemission/RIXS sample-orientation stages (azimuth/polar/tilt) | ALREADY graduated (NSLS-II esm). Diamond reinforces it and sharpens the discrimination: these bind Manipulator, NOT the MX Goniometer (different contract). No action. |
| GratingMonochromator | 4 (i05, i09, i21, b07) | soft-X-ray PGMs | ALREADY graduated (NSLS-II csx). 4 Diamond consumers. No action. |
| Goniometer | 3 (i04, i02-1, i23) | the Diamond MX set (Smargon, XYZWrappedOmega, SixAxisGonio) | ALREADY graduated (i03). Note the THREE variants (full Smargon i04, constrained-omega i02-1, six-axis i23): all bind Goniometer but the constrained-omega case (i02-1) is flagged to confirm family-vs-composition. No action; variant question noted. |
| TemperatureController | 6 (i04 thawer?, i05, i09, i16, i21, b21) | Lakeshore 336/340, Linkam | ALREADY graduated. i16 broadens it with the LS340 model; i04's Thawer is flagged as a confirm (may be momentary, not a true Regulator). No action. |
| FlowController | 1 (b21 Vici valves) | first Diamond flow actuator | ALREADY graduated (NSLS-II). b21's Vici valves would be the first Diamond consumer if confirmed; reinforces cross-facility, no action. |

**Net over the 14:** zero new families. The only loose binding is `Backlight` (i04, single-use). The fleet stressed the vocabulary across MX, ARPES, HAXPES, RIXS, surface diffraction, magnetism, XAS, BioSAXS, and imaging+diffraction, and it held. This is the generalization result the Diamond exercise was designed to produce.

## Negative results (recorded for the cross-facility picture)

- **SpectrometerArm stays a watch at n=2.** i21 (RIXS) was the candidate to take it to rule-of-three, but its spectrometer arm is absent from public dodal (SPEC-1). It does NOT trigger graduation.
- **energy_scan Capability remains unsatisfiable from dodal.** b18 (the core XAS beamline) was the candidate to provide the instantiated scanning DCM the pending energy_scan graduation wants; b18's dodal module is a stub (no DCM). Confirmed the survey's read.
- **Diffractometer**: i07, i16, k11 all have an absent diffractometer (DIFF-1). When those land in dodal they would feed the fleet-wide Diffractometer graduation question (NSLS-II has it loose at n=6), but they are not modellable today, so Diamond does not yet move that needle.

## Recurring loose-family / DIAG notes

- **GenericProbe (10/14)** absorbs the unresolved sensors: XBPM feedback, synchrotron status, pin-tip vision, quadrant diodes, intensity-protection, dual-energy source-selectors. The `DIAG-1` cluster, held by design.
- **Backlight (i04)** is the one single-use loose binding; no signal.

## Provenance

Compiled from the device tables of the 14 device-passed Diamond beamlines (every PV verified verbatim against `DiamondLightSource/dodal` at pass time; six partial/stub modules flagged their absent instruments as open questions). Method: per-beamline distinct "Suggested family" values, `(?)` suffixes stripped, counted across beamlines. The 10 original deployments' device data lives in their `deployments/<bl>/beamline.yaml`; fold them in here if they are ever given Tier-2 facts passes. The durable headline is the generalization result: CORA's families, shaped at APS + NSLS-II, hold at Diamond with zero new families earned.
