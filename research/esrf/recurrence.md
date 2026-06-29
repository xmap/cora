# Fleet recurrence: ESRF

Cross-fleet device-class frequency across the ESRF beamlines surveyed under `research/esrf/beamlines/`. The point of this report is the **catalog Family graduation signal**: a device class that recurs across two or more *physically distinct* beamlines is a graduation candidate (rule-of-three is the firm trigger; two is a watch). `graduated` marks classes already in `catalog/catalog.yaml`.

ESRF is a BLISS / Tango facility, so there is no `scripts/reverse_engineer` extractor for it (that tool is EPICS / `*-bits`-specific); this file is filled by hand from the per-beamline `facts.md` device inventories and new-family-watch sections.

!!! warning "Count physical beamlines, not repos"
    Each ESRF beamline publishes one `beamline_configuration` repo, so repo count equals beamline count here; no fork or multi-endstation collapse was needed. ID19 (microtomography), ID16B (nano-imaging), ID28 (IXS), and ID32 (soft X-ray RIXS / XMCD) are four physically distinct beamlines. ID32 has two endstations (RIXS + XMCD) in one config; that is one beamline, one data point.

## Beamlines folded in so far

| Beamline | Science | Source commit | Note |
| --- | --- | --- | --- |
| ID19 | microtomography / laminography / radiography | `b78389a` | shipped deployment; older multi-table facts format |
| ID16B | nano-imaging (holotomography + nano-XRF) | (per its facts.md) | shipped deployment; older multi-table facts format |
| ID28 | momentum-resolved IXS | `85fe3f3` | shipped deployment |
| ID32 | soft X-ray RIXS / XMCD / XES | `e14bef4` | shipped deployment; this pass |

The remaining public-config ESRF beamlines (ID06, BM23, BM25, BM26) are not yet folded in; their counts will move when their passes land.

## Suggested families by beamline count

Presence per beamline (an Asset of that Family appears at least once), not device count. Across the four beamlines folded in so far:

| Family | Beamlines | Status |
| --- | --- | --- |
| Slit | 4 (id19, id16b, id28, id32) | graduated |
| Shutter | 4 (id19, id16b, id28, id32) | graduated |
| LinearStage | 4 (id19, id16b, id28, id32) | graduated |
| Camera | 4 (id19, id16b, id28, id32) | graduated |
| InsertionDevice | 4 (id19, id16b, id28, id32) | graduated |
| Monochromator | 3 (id19, id16b, id28) | graduated |
| PseudoAxis | 2 (id28, id32) | graduated |
| TemperatureController | 2 (id28, id32) | graduated |
| Goniometer (?) | 2 (id28, id32) | graduated (id28 binding confirm vs LinearStage, SAMPLE-1; id32 4-circle DiffE4CH) |
| Screen (?) | 2 (id28, id32) | graduated (binding confirm vs FluxMonitor diode) |
| RotaryStage | 2 (id19, id16b) | graduated |
| Mirror | 2 (id16b, id28) | graduated |
| Transfocator | 2 (id19, id28) | graduated |
| FluxMonitor | 2 (id16b, id28) | graduated |
| StorageRing | 2 (id28, id32) | loose (MACHINE-1) |
| TimingController (?) | 2 (id28, id32) | graduated (binding confirm; vs GenericProbe) |
| SpectrometerArm | 1 beamline, 2 arms (id32 RIXS + XES) | loose (RIXS-1); grating-dispersive lineage |
| GenericProbe (?) | 2 (id28, id32) | loose |
| GratingMonochromator | 1 (id32) | graduated |
| Magnet | 1 (id32) | loose (MAG-1) |
| PolarizationAnalyzer | 1 (id32) | loose (POL-2) |
| FlowController | 1 (id32) | graduated |
| EnergyDispersiveSpectrometer | 1 (id16b) | graduated |
| Filter | 1 (id19) | graduated |
| EnergyAnalyzer | 1 (id28) | loose (ANALYZER-1); crystal-analyzer lineage |
| BeamPositionMonitor | 1 (id28) | loose (DIAG-1) |
| (microscope optics) | 1 (id19) | unmapped; tomography objective/scintillator turret, see id19 facts |

Every Family that ID28 and ID32 bind to a graduated catalog entry stays graduated; neither coins anything.

!!! note "ID32 reaches the SpectrometerArm rule-of-three on its own, but it stays HELD"
    ID32 instantiates the same `SpectrometerArmsController` class twice (the RIXS arm and the XES arm), so with the SIX soft-RIXS arm the grating-dispersive `SpectrometerArm` family is sighted three times. Per the owner decision recorded in the shipped descriptor it is HELD, not graduated, here (RIXS-1); graduation is a separate gated catalog PR, never a research fold. Critically, this is the **grating-dispersive** lineage and is distinct from ID28's **crystal-analyzer** arm (the loose `EnergyAnalyzer`, ANALYZER-1). The two ESRF inelastic beamlines do NOT stack onto one count.

## Device classes by beamline count

The raw BLISS controller class names seen in source, before mapping to a CORA Family. ESRF classes are largely beamline-specific (each beamline ships its own `id28.controllers.*` / `id32.controllers.*` package), so cross-beamline class-name recurrence is weak; the shared classes are the BLISS-core and IcePAP primitives.

| Source class | Beamlines |
| --- | --- |
| `IcePAP` | 4 (id19, id16b, id28, id32) |
| `Lima` | 4 (id19, id16b, id28, id32) |
| `ESRF_Undulator` | 4 (id19, id16b, id28, id32) |
| `TangoShutter` | 2+ (id28, id32 confirmed; id19 records it in handles) |
| `musst` | 2 (id28, id32) |
| `EBV` | 2 (id28, id32) |
| `slits` | 2+ (id28, id32 confirmed; id19/id16b use slit calc, class not recorded in older facts) |
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
| `CT2` (P201) | 2 (id28, id32) |

## Graduation shortlist (the actionable output)

The classes that recur across distinct beamlines AND are not yet a catalog Family. From the four ESRF beamlines folded in so far, **nothing clears the rule-of-three that is not already graduated or already held under an owner decision.** Watches:

| Candidate Family | Distinct beamlines | Discriminator (what it is that no existing Family covers) | Blocker / note |
| --- | --- | --- | --- |
| SpectrometerArm | 1 ESRF beamline, 2 arms (id32 RIXS + XES) + SIX | grating-dispersive soft X-ray Rowland spectrometer arm (distinct from the crystal-analyzer EnergyAnalyzer and the crystal-emission EnergyDispersiveSpectrometer) | LOOSE, HELD under `RIXS-1` per the shipped-descriptor owner decision; reaches rule-of-three (RIXS arm + XES arm + SIX) but graduation is a separate gated catalog PR, never a research fold. Do not coin here. |
| EnergyAnalyzer | 1 ESRF (id28) + LCLS-MFX / ISS near-cousins | IXS diced-crystal analyzer arm selecting a fixed final energy on the inelastic-scattering two-theta arm (distinct from grating-dispersive SpectrometerArm and from the crystal-emission EnergyDispersiveSpectrometer) | LOOSE, held under `ANALYZER-1`; only one ESRF sighting; cross-facility count is the live question. NOTE the shipped `deployments/id28/beamline.yaml` binds this Asset to `SpectrometerArm` (RIXS-1) instead; the catalog note assigns the IXS crystal-analyzer arm to `EnergyAnalyzer` (ANALYZER-1). Resolve which loose family ID28 reinforces before either graduates. Do not coin from ID28. |
| Magnet | 1 ESRF (id32) + 4-ID + i10-1 | high-field superconducting sample magnet (settable field axis) | LOOSE, HELD under `MAG-1` per the shipped descriptor (third consumer); graduation deferred to a gated PR. Do not coin. |
| PolarizationAnalyzer | 1 ESRF (id32) + 4-ID + i10 | scattered-beam polarization-analysis block | LOOSE, HELD under `POL-2` per the shipped descriptor (third consumer); graduation deferred. Do not coin. |
| BeamPositionMonitor | 1 ESRF (id28) + fleet-wide | beam-centroid position monitor (distinct from FluxMonitor by what it measures, position not flux) | LOOSE, held fleet-wide under `DIAG-1`; do not coin |

One paragraph on the most overdue: nothing among the ESRF beamlines is overdue for a research-driven graduation, because the three families that have actually reached a rule-of-three (`SpectrometerArm` via ID32's two arms + SIX, plus `Magnet` and `PolarizationAnalyzer` at their third consumers) are all already HELD under explicit owner decisions recorded in the shipped ID32 descriptor (RIXS-1, MAG-1, POL-2); their graduations are deferred to dedicated gate-reviewed catalog PRs by design, not blocked for lack of evidence. The genuinely open question the ESRF set surfaces is a *disambiguation*, not a graduation: ID28's IXS arm is a crystal analyzer (`EnergyAnalyzer`, ANALYZER-1) while ID32's RIXS / XES arms are grating-dispersive (`SpectrometerArm`, RIXS-1), yet the shipped ID28 descriptor binds its arm to `SpectrometerArm`. Reconciling that (do the two inelastic beamlines reinforce one loose family or two distinct ones?) belongs to a modeling pass over the catalog and the two descriptors, not to this research fold.
