# Fleet recurrence: ESRF

Cross-fleet device-class frequency across the ESRF beamlines surveyed under `research/esrf/beamlines/`. The point of this report is the **catalog Family graduation signal**: a device class that recurs across two or more *physically distinct* beamlines is a graduation candidate (rule-of-three is the firm trigger; two is a watch). `graduated` marks classes already in `catalog/catalog.yaml`.

ESRF is a BLISS / Tango facility, so there is no `scripts/reverse_engineer` extractor for it (that tool is EPICS / `*-bits`-specific); this file is filled by hand from the per-beamline `facts.md` device inventories and new-family-watch sections.

!!! warning "Count physical beamlines, not repos"
    Each ESRF beamline publishes one `beamline_configuration` repo, so repo count equals beamline count here; no fork or multi-endstation collapse was needed. ID19 (microtomography), ID16B (nano-imaging), and ID28 (IXS) are three physically distinct beamlines.

## Beamlines folded in so far

| Beamline | Science | Source commit | Note |
| --- | --- | --- | --- |
| ID19 | microtomography / laminography / radiography | `b78389a` | shipped deployment; older multi-table facts format |
| ID16B | nano-imaging (holotomography + nano-XRF) | (per its facts.md) | shipped deployment; older multi-table facts format |
| ID28 | momentum-resolved IXS | `85fe3f3` | shipped deployment; this pass |

The remaining public-config ESRF beamlines (ID06, ID32, BM23, BM25, BM26) are not yet folded in; their counts will move when their passes land.

## Suggested families by beamline count

Presence per beamline (an Asset of that Family appears at least once), not device count. Across the three beamlines folded in so far:

| Family | Beamlines | Status |
| --- | --- | --- |
| Monochromator | 3 (id19, id16b, id28) | graduated |
| Slit | 3 (id19, id16b, id28) | graduated |
| Shutter | 3 (id19, id16b, id28) | graduated |
| LinearStage | 3 (id19, id16b, id28) | graduated |
| Camera | 3 (id19, id16b, id28) | graduated |
| InsertionDevice | 3 (id19, id16b, id28) | graduated |
| RotaryStage | 2 (id19, id16b) | graduated |
| Mirror | 2 (id16b, id28) | graduated |
| Transfocator | 2 (id19, id28) | graduated |
| FluxMonitor | 2 (id16b, id28) | graduated |
| EnergyDispersiveSpectrometer | 1 (id16b) | graduated |
| Filter | 1 (id19) | graduated |
| TemperatureController | 1 (id28) | graduated |
| Goniometer (?) | 1 (id28) | graduated (binding confirm; vs LinearStage, SAMPLE-1) |
| Screen (?) | 1 (id28) | graduated (binding confirm) |
| PseudoAxis | 1 (id28) | graduated |
| EnergyAnalyzer | 1 (id28) | loose (ANALYZER-1) |
| BeamPositionMonitor | 1 (id28) | loose (DIAG-1) |
| StorageRing | 1 (id28) | loose (MACHINE-1) |
| TimingController (?) | 1 (id28) | graduated (binding confirm; vs GenericProbe) |
| GenericProbe (?) | 1 (id28) | loose |
| (microscope optics) | 1 (id19) | unmapped; tomography objective/scintillator turret, see id19 facts |

Every Family that ID28 binds to a graduated catalog entry stays graduated; ID28 coins nothing.

## Device classes by beamline count

The raw BLISS controller class names seen in source, before mapping to a CORA Family. ESRF classes are largely beamline-specific (each beamline ships its own `id28.controllers.*` package), so cross-beamline class-name recurrence is weak; the shared classes are the BLISS-core and IcePAP primitives.

| Source class | Beamlines |
| --- | --- |
| `IcePAP` | 3 (id19, id16b, id28) |
| `Lima` | 3 (id19, id16b, id28) |
| `ESRF_Undulator` | 3 (id19, id16b, id28) |
| `slits` | 1+ (id28 confirmed; id19/id16b use slit calc, class not recorded in older facts) |
| `TangoShutter` | 1+ (id28 confirmed; id19 records `TangoShutter` in handles) |
| `TwoThetaMultilayer` | 1 (id28) |
| `InclinedAnalyser` | 1 (id28) |
| `CylSlit` | 1 (id28) |
| `PI_E518` | 1 (id28) |
| `F700` | 1 (id28) |
| `SmarAct_MCS2` | 1 (id28) |
| `AMC100` | 1 (id28) |
| `EBV` | 1 (id28) |
| `LakeShore340` | 1 (id28) |
| `musst` | 1 (id28) |
| `CT2` (P201) | 1 (id28) |

## Graduation shortlist (the actionable output)

The classes that recur across distinct beamlines AND are not yet a catalog Family. From the three ESRF beamlines folded in so far, **nothing clears the rule-of-three that is not already graduated.** Watches:

| Candidate Family | Distinct beamlines | Discriminator (what it is that no existing Family covers) | Blocker / note |
| --- | --- | --- | --- |
| EnergyAnalyzer | 1 ESRF (id28) + LCLS-MFX / ISS near-cousins | IXS diced-crystal analyzer arm selecting a fixed final energy on the inelastic-scattering two-theta arm (distinct from grating-dispersive SpectrometerArm and from the crystal-emission EnergyDispersiveSpectrometer) | LOOSE, held under `ANALYZER-1`; only one ESRF sighting; cross-facility count is the live question. NOTE the shipped `deployments/id28/beamline.yaml` binds this Asset to `SpectrometerArm` (RIXS-1) instead; the catalog note assigns the IXS crystal-analyzer arm to `EnergyAnalyzer` (ANALYZER-1). Resolve which loose family ID28 reinforces before either graduates. Do not coin from ID28. |
| BeamPositionMonitor | 1 ESRF (id28) + fleet-wide | beam-centroid position monitor (distinct from FluxMonitor by what it measures, position not flux) | LOOSE, held fleet-wide under `DIAG-1`; do not coin |

One paragraph on the most overdue: nothing among the ESRF beamlines is overdue for graduation. The ESRF set so far only *reinforces* already-graduated families (Monochromator, Slit, Shutter, LinearStage, Camera, InsertionDevice all hit three ESRF beamlines but are long graduated) and adds two further sightings to loose families that are held under cross-facility reviews (`ANALYZER-1`, `DIAG-1`). The one decision ID28 forces is not a graduation but a *disambiguation*: whether the IXS analyzer arm is the `EnergyAnalyzer` or `SpectrometerArm` lineage. That belongs to a modeling pass that reconciles the shipped descriptor with the catalog note, not to a scaffold, and certainly not to this research fold.
