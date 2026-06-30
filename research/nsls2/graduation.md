# Catalog graduation decisions: NSLS-II

Step 2 of the roadmap (survey -> recurrence -> graduation): take the recurring candidates from
`recurrence.md` through an intentional graduate / model-as-Assembly / fold / leave-loose
decision, with the naming-r3 gate applied to every name a future graduation would use. The
authority for "graduated" is `catalog/catalog.yaml`, not this page or the survey prose; where
they disagree, the catalog wins.

## The honest outcome: no new Family earned by the NSLS-II pass

The 11-beamline NSLS-II pass (bmm, srx, iss, chx, fxi, pdf, hxn, cms, xpd, ios, fmx) overwhelmingly
reuses existing catalog vocabulary rather than demanding new Families. That is the intended
result: the fleet stresses the existing abstractions and they hold. Every recurring class is
already a graduated Family, an Assembly, or a deliberately-held loose family pending a
cross-facility review.

## Decisions

| Candidate | Distinct beamlines | CORA status (per catalog) | Decision | naming-r3 |
| --- | --- | --- | --- | --- |
| Diffractometer | 3 (chx, hxn, xpd) | Assembly (composes Goniometer + RotaryStage arms + PseudoAxis) | model as Assembly, not a Family; same call as the APS pass | `Diffractometer` passes (Assembly) |
| TemperatureController | 5 (chx, cms, fxi, pdf, xpd) | GRADUATED (presents Regulator) | reinforce only; pdf + xpd each bind 3+ mechanisms (Lakeshore, Linkam, Eurotherm, CS800). Strongest confirmation in the fleet | passes (`<Domain>Controller`) |
| FlowController | 2 (chx, xpd) | GRADUATED (presents Regulator) | reinforce only; chx + xpd syringe pumps add to the cross-facility consumers (Diamond i22 / 7-bm / lix / xfp) | passes |
| TimingController | 4 (chx, fmx, fxi, srx) | GRADUATED | reinforce; every Zebra was tagged `(?)` "confirm timing role" at pass time, a confirmation task, not a graduation | passes |
| Transfocator | 2 (here) | GRADUATED | reinforce (rule-of-three met across the wider fleet) | passes (prefer over `CompoundRefractiveLens`) |
| Manipulator | ESM | GRADUATED | earned here (first ARPES manipulator) | passes |
| GratingMonochromator | CSX | GRADUATED | earned here | passes |
| ElectronAnalyzer | esm + sst | GRADUATED | earned here | passes (spelled-out form) |
| EmissionSpectrometer | iss (Johann + von Hamos) | GRADUATED | 2 device consumers on ONE beamline; clarify vs the loose SpectrometerArm when a 2nd RIXS lands | passes |
| EnergyAnalyzer | IXS | LOOSE (not in catalog) | hold; the IXS multi-analyzer arm, half of the EnergyAnalyzer-vs-SpectrometerArm disambiguation | spelled-out form passes |
| SpectrometerArm | n=1 (RIXS) | LOOSE (not in catalog) | hold at n=1; needs a second RIXS beamline to fire the rule-of-three | passes |

## Recurring loose-family / DIAG notes

- **GenericProbe (11/11)** absorbs the fleet-wide unresolved sensors: BPMs, scalers, current
  preamps, electrometers, gas analyzers, viewing cameras. This is the `DIAG-1` cluster
  (beam-position fragmentation across BeamPositionMonitor / Diagnostic / GenericProbe) plus
  scalers and preamps. Held by design pending the cross-facility DIAG abstraction review; do not
  graduate piecemeal.
- **Microscope / BetrandLens / Screen** are single-use loose bindings; no signal.

## Scope and provenance

Covers the 11 beamlines device-passed so far. The remaining 13 (amx, cdi, csx, esm, hex, isr,
ixs, lix, six, smi, sst, xfm) are not yet passed; revisit when they land, since the
EnergyAnalyzer / SpectrometerArm disambiguation in particular turns on a second RIXS beamline.
Counts are distinct physical beamlines, not repos; see `recurrence.md` for the per-class table.
