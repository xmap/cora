# Fleet recurrence: ESRF

Cross-fleet device-class frequency across the ESRF beamlines surveyed under `research/esrf/beamlines/`. The point of this report is the **catalog Family graduation signal**: a device class that recurs across two or more *physically distinct* beamlines is a graduation candidate (rule-of-three is the firm trigger; two is a watch). `graduated` marks classes already in `catalog/catalog.yaml`.

ESRF is a BLISS / Tango facility, so there is no `scripts/reverse_engineer` extractor for it (that tool is EPICS / `*-bits`-specific); this file is filled by hand from the per-beamline `facts.md` device inventories and new-family-watch sections.

!!! warning "Count physical beamlines, not repos"
    Each ESRF beamline publishes one `beamline_configuration` repo, so repo count equals beamline count here; no fork or multi-endstation collapse was needed. ID19 (microtomography), ID16B (nano-imaging), ID28 (IXS), ID32 (soft X-ray RIXS / XMCD), and ID06 (DFXM / X-ray optics / large-volume press) are five physically distinct beamlines. ID32 has two endstations (RIXS + XMCD) and ID06 several technique sessions (DEG / XOG / LVP / EH1 / EH2) in one config each; each is one beamline, one data point.

## Beamlines folded in so far

| Beamline | Science | Source commit | Note |
| --- | --- | --- | --- |
| ID19 | microtomography / laminography / radiography | `b78389a` | shipped deployment; older multi-table facts format |
| ID16B | nano-imaging (holotomography + nano-XRF) | (per its facts.md) | shipped deployment; older multi-table facts format |
| ID28 | momentum-resolved IXS | `85fe3f3` | shipped deployment |
| ID32 | soft X-ray RIXS / XMCD / XES | `e14bef4` | shipped deployment |
| ID06 | DFXM / X-ray optics testing / large-volume press | `19bad8a` | NOT yet a deployment; this pass |

The remaining public-config ESRF beamlines (BM23, BM25, BM26) are not yet folded in; their counts will move when their passes land.

## Suggested families by beamline count

Presence per beamline (an Asset of that Family appears at least once), not device count. Across the five beamlines folded in so far:

| Family | Beamlines | Status |
| --- | --- | --- |
| Slit | 5 (id19, id16b, id28, id32, id06) | graduated |
| Shutter | 5 (id19, id16b, id28, id32, id06) | graduated |
| LinearStage | 5 (id19, id16b, id28, id32, id06) | graduated |
| Camera | 5 (id19, id16b, id28, id32, id06) | graduated |
| InsertionDevice | 5 (id19, id16b, id28, id32, id06) | graduated |
| Monochromator | 4 (id19, id16b, id28, id06) | graduated |
| Transfocator | 3 (id19, id28, id06) | graduated |
| FluxMonitor | 3 (id16b, id28, id06) | graduated |
| TemperatureController | 3 (id28, id32, id06) | graduated |
| StorageRing | 3 (id28, id32, id06) | loose (MACHINE-1) |
| TimingController (?) | 3 (id28, id32, id06) | graduated (binding confirm; vs GenericProbe) |
| GenericProbe (?) | 3 (id28, id32, id06) | loose |
| PseudoAxis | 2 (id28, id32) | graduated |
| Goniometer (?) | 2 (id28, id32) | graduated (id28 binding confirm vs LinearStage, SAMPLE-1; id32 4-circle DiffE4CH) |
| Screen (?) | 2 (id28, id32) | graduated (binding confirm vs FluxMonitor diode) |
| RotaryStage | 2 (id19, id16b) | graduated |
| Mirror | 2 (id16b, id28) | graduated |
| Filter | 2 (id19, id06) | graduated |
| SpectrometerArm | 1 beamline, 2 arms (id32 RIXS + XES) | loose (RIXS-1); grating-dispersive lineage |
| GratingMonochromator | 1 (id32) | graduated |
| Magnet | 1 (id32) | loose (MAG-1) |
| PolarizationAnalyzer | 1 (id32) | loose (POL-2) |
| FlowController | 1 (id32) | graduated |
| EnergyDispersiveSpectrometer | 1 (id16b) | graduated |
| EnergyAnalyzer | 1 (id28) | loose (ANALYZER-1); crystal-analyzer lineage |
| BeamPositionMonitor | 1 (id28) | loose (DIAG-1) |
| Controller / MonoFeedback (?) | 1 (id06) | Role not Family; MOCO beam-stabilization (fleet-wide MonoFeedback watch) |
| LargeVolumePress | 0 devices (id06 technique) | NOT a family: technique present, NO press device in public source (PRESS-1) |
| (microscope optics) | 1 (id19) | unmapped; tomography objective/scintillator turret, see id19 facts |

Every Family that ID28, ID32, and ID06 bind to a graduated catalog entry stays graduated; none coins anything.

!!! note "ID32 reaches the SpectrometerArm rule-of-three on its own, but it stays HELD"
    ID32 instantiates the same `SpectrometerArmsController` class twice (the RIXS arm and the XES arm), so with the SIX soft-RIXS arm the grating-dispersive `SpectrometerArm` family is sighted three times. Per the owner decision recorded in the shipped descriptor it is HELD, not graduated, here (RIXS-1); graduation is a separate gated catalog PR, never a research fold. Critically, this is the **grating-dispersive** lineage and is distinct from ID28's **crystal-analyzer** arm (the loose `EnergyAnalyzer`, ANALYZER-1). The two ESRF inelastic beamlines do NOT stack onto one count.

## Device classes by beamline count

The raw BLISS controller class names seen in source, before mapping to a CORA Family. ESRF classes are largely beamline-specific (each beamline ships its own `id28.controllers.*` / `id32.controllers.*` package), so cross-beamline class-name recurrence is weak; the shared classes are the BLISS-core and IcePAP primitives.

| Source class | Beamlines |
| --- | --- |
| `IcePAP` | 5 (id19, id16b, id28, id32, id06) |
| `Lima` | 5 (id19, id16b, id28, id32, id06) |
| `ESRF_Undulator` | 5 (id19, id16b, id28, id32, id06) |
| `TangoShutter` | 3+ (id28, id32, id06 confirmed; id19 records it in handles) |
| `musst` | 3 (id28, id32, id06) |
| `slits` | 3+ (id28, id32, id06 confirmed; id19/id16b use slit calc, class not recorded in older facts) |
| `Nanodac` | 2 (id28, id06) |
| `EBV` | 2 (id28, id32) |
| `CT2` (P201) | 3 (id28, id32, id06) |
| `Moco` | 1 (id06) |
| `ID06mono` | 1 (id06) |
| `TransfocatorID06` | 1 (id06) |
| `PI_E727` | 1 (id06) |
| `Nhq` | 1 (id06) |
| `SphirdBlissController` / `XiderBlissController` | 1 (id06, deg_bliss firewalled) |
| `SpectrometerArmsController` | 1 (id32, two instances) |
| `MonochromatorGrating` | 1 (id32) |
| `CryogenicPSController` | 1 (id32) |
| `Bronkhorst` | 1 (id32) |
| `esrf_hexapode` | 1 (id32) |
| `PI_E753` | 1 (id32) |
| `DiffE4CH` | 1 (id32) |
| `TwoThetaMultilayer` | 1 (id28) |
| `InclinedAnalyser` | 1 (id28) |
| `CylSlit` | 1 (id28) |
| `PI_E518` | 1 (id28) |
| `F700` | 1 (id28) |
| `SmarAct_MCS2` | 1 (id28) |
| `AMC100` | 1 (id28) |
| `LakeShore340` | 2 (id28, id32) |
| `LakeShore336TangoInput` | 1 (id32) |

## Graduation shortlist (the actionable output)

The classes that recur across distinct beamlines AND are not yet a catalog Family. From the five ESRF beamlines folded in so far, **nothing clears the rule-of-three that is not already graduated or already held under an owner decision.** Watches:

| Candidate Family | Distinct beamlines | Discriminator (what it is that no existing Family covers) | Blocker / note |
| --- | --- | --- | --- |
| SpectrometerArm | 1 ESRF beamline, 2 arms (id32 RIXS + XES) + SIX | grating-dispersive soft X-ray Rowland spectrometer arm (distinct from the crystal-analyzer EnergyAnalyzer and the crystal-emission EnergyDispersiveSpectrometer) | LOOSE, HELD under `RIXS-1` per the shipped-descriptor owner decision; reaches rule-of-three (RIXS arm + XES arm + SIX) but graduation is a separate gated catalog PR, never a research fold. Do not coin here. |
| EnergyAnalyzer | 1 ESRF (id28) + LCLS-MFX / ISS near-cousins | IXS diced-crystal analyzer arm selecting a fixed final energy on the inelastic-scattering two-theta arm (distinct from grating-dispersive SpectrometerArm and from the crystal-emission EnergyDispersiveSpectrometer) | LOOSE, held under `ANALYZER-1`; only one ESRF sighting; cross-facility count is the live question. NOTE the shipped `deployments/id28/beamline.yaml` binds this Asset to `SpectrometerArm` (RIXS-1) instead; the catalog note assigns the IXS crystal-analyzer arm to `EnergyAnalyzer` (ANALYZER-1). Resolve which loose family ID28 reinforces before either graduates. Do not coin from ID28. |
| Magnet | 1 ESRF (id32) + 4-ID + i10-1 | high-field superconducting sample magnet (settable field axis) | LOOSE, HELD under `MAG-1` per the shipped descriptor (third consumer); graduation deferred to a gated PR. Do not coin. |
| PolarizationAnalyzer | 1 ESRF (id32) + 4-ID + i10 | scattered-beam polarization-analysis block | LOOSE, HELD under `POL-2` per the shipped descriptor (third consumer); graduation deferred. Do not coin. |
| BeamPositionMonitor | 1 ESRF (id28) + fleet-wide | beam-centroid position monitor (distinct from FluxMonitor by what it measures, position not flux) | LOOSE, held fleet-wide under `DIAG-1`; do not coin |
| LargeVolumePress | 0 devices (id06 names the technique) | multi-anvil hydraulic GPa-pressure sample environment, no existing Family covers it | NOT a candidate yet: ID06 runs an `LVP` session and an `id06-lvp` scan-saving name, but the public config instantiates NO press / ram / anvil / load-cell controller, only generic IcePAP stages + a view camera. A technique without a device in source. Open question `PRESS-1`; needs the controller in source or staff confirmation before it is even a one-sighting watch. Do not coin, do not infer. |
| Controller / MonoFeedback | 1 ESRF (id06) + fleet-wide | monochromator beam-position stabilization feedback (MOCO box) | `Controller` is a catalog Role, not a Family; MOCO-style feedback recurs (APS `MonoFeedback`). Confirm Family binding; do not coin from id06. |

One paragraph on the most overdue: nothing among the ESRF beamlines is overdue for a research-driven graduation, because the three families that have actually reached a rule-of-three (`SpectrometerArm` via ID32's two arms + SIX, plus `Magnet` and `PolarizationAnalyzer` at their third consumers) are all already HELD under explicit owner decisions recorded in the shipped ID32 descriptor (RIXS-1, MAG-1, POL-2); their graduations are deferred to dedicated gate-reviewed catalog PRs by design, not blocked for lack of evidence. The genuinely open question the ESRF set surfaces is a *disambiguation*, not a graduation: ID28's IXS arm is a crystal analyzer (`EnergyAnalyzer`, ANALYZER-1) while ID32's RIXS / XES arms are grating-dispersive (`SpectrometerArm`, RIXS-1), yet the shipped ID28 descriptor binds its arm to `SpectrometerArm`. Reconciling that (do the two inelastic beamlines reinforce one loose family or two distinct ones?) belongs to a modeling pass over the catalog and the two descriptors, not to this research fold.

A note on ID06 and the `LargeVolumePress` non-candidate: ID06 is the clearest example in this set of the practice's "technique without a device in source" case. The beamline plainly runs a large-volume press (a dedicated `LVP` BLISS session, an `id06-lvp` scan-saving root), which would be a genuinely novel sample-environment Family. But the public Beacon config instantiates no press / ram / anvil / load-cell controller, only the generic IcePAP stages and a view camera the press is mounted on. Coining a `LargeVolumePress` Family from a session name and a scan-saving string, with no instantiated device, would be exactly the invention the practice forbids. It is recorded as `PRESS-1` (ask staff or wait for the controller to appear in source), not as a one-sighting watch. The same discipline applies to the DEG DFXM detectors (`Sphird` / `Xider`) and the `bcdu8` beam-conditioning unit, whose controller classes live in the private `deg_bliss` package: named in source, but the device contract is firewalled (`DEG-1`).
