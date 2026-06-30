# Fleet recurrence: ESRF

Cross-fleet device-class frequency across the ESRF beamlines surveyed under `research/esrf/beamlines/`. The point of this report is the **catalog Family graduation signal**: a device class that recurs across two or more *physically distinct* beamlines is a graduation candidate (rule-of-three is the firm trigger; two is a watch). `graduated` marks classes already in `catalog/catalog.yaml`.

ESRF is a BLISS / Tango facility, so there is no `scripts/reverse_engineer` extractor for it (that tool is EPICS / `*-bits`-specific); this file is filled by hand from the per-beamline `facts.md` device inventories and new-family-watch sections.

!!! warning "Count physical beamlines, not repos"
    Each ESRF beamline publishes one `beamline_configuration` repo, so repo count equals beamline count here; no fork or multi-endstation collapse was needed. ID19 (microtomography), ID16B (nano-imaging), ID28 (IXS), ID32 (soft X-ray RIXS / XMCD), ID06 (DFXM / X-ray optics / large-volume press), BM26 (DUBBLE CRG SAXS/WAXS/XAFS), BM25 (SpLine CRG XRD/XAS), and BM23 (XAS / EXAFS + XES) are eight physically distinct beamlines. This is the COMPLETE public-config ESRF set as of 2026-06 (every `<beamline>/beamline_configuration` repo public on gitlab.esrf.fr). ID32 has two endstations and ID06 several technique sessions in one config each; each is one beamline, one data point. BM26 / BM25 / BM23 are bending-magnet beamlines (no insertion device). Two caveats on the per-beamline weight: BM25's public config is a partial mirror (detectors + sample environment only), and BM23's is stale (2022 snapshot); both are flagged in their facts.md and weighted accordingly below.

## Beamlines folded in so far

| Beamline | Science | Source commit | Note |
| --- | --- | --- | --- |
| ID19 | microtomography / laminography / radiography | `b78389a` | shipped deployment; older multi-table facts format |
| ID16B | nano-imaging (holotomography + nano-XRF) | (per its facts.md) | shipped deployment; older multi-table facts format |
| ID28 | momentum-resolved IXS | `85fe3f3` | shipped deployment |
| ID32 | soft X-ray RIXS / XMCD / XES | `e14bef4` | shipped deployment |
| ID06 | DFXM / X-ray optics testing / large-volume press | `19bad8a` | NOT yet a deployment |
| BM26 | DUBBLE CRG: SAXS / WAXS + XAFS (bending magnet) | `bf4899a` | NOT yet a deployment |
| BM25 | SpLine CRG: XRD / XAS (bending magnet) | `81da855` | NOT yet a deployment. PARTIAL public config (detectors + sample env only) |
| BM23 | XAS / EXAFS + XES (bending magnet) | `8bf008c` | NOT yet a deployment; this pass. STALE config (2022 snapshot) |

This completes the public-config ESRF set (ID06, ID16B, ID19, ID28, ID32, BM23, BM25, BM26). No further ESRF beamline publishes a Beacon config as of 2026-06.

## Suggested families by beamline count

Presence per beamline (an Asset of that Family appears at least once), not device count. Across all eight beamlines. BM25 (partial config) contributes to only Camera / EnergyDispersiveSpectrometer / TemperatureController / GenericProbe; BM23 (stale) contributes its full XAS topology.

| Family | Beamlines | Status |
| --- | --- | --- |
| Camera | 8 (id19, id16b, id28, id32, id06, bm26, bm25, bm23) | graduated |
| Slit | 7 (id19, id16b, id28, id32, id06, bm26, bm23) | graduated |
| Shutter | 7 (id19, id16b, id28, id32, id06, bm26, bm23) | graduated |
| LinearStage | 7 (id19, id16b, id28, id32, id06, bm26, bm23) | graduated |
| Monochromator | 6 (id19, id16b, id28, id06, bm26, bm23) | graduated |
| TemperatureController | 6 (id28, id32, id06, bm26, bm25, bm23) | graduated |
| GenericProbe (?) | 6 (id28, id32, id06, bm26, bm25, bm23) | loose |
| FluxMonitor | 5 (id16b, id28, id06, bm26, bm23) | graduated |
| InsertionDevice | 5 (id19, id16b, id28, id32, id06) | graduated (NOT bm26/bm25/bm23: bending magnet) |
| StorageRing | 5 (id28, id32, id06, bm26, bm23) | loose (MACHINE-1) |
| TimingController (?) | 5 (id28, id32, id06, bm26, bm23) | graduated (binding confirm; vs GenericProbe) |
| Mirror | 4 (id16b, id28, bm26, bm23) | graduated |
| Screen (?) | 4 (id28, id32, bm26, bm23) | graduated (binding confirm vs FluxMonitor diode) |
| EnergyDispersiveSpectrometer | 3 (id16b, bm25, bm23) | graduated |
| Transfocator | 3 (id19, id28, id06) | graduated |
| EmissionSpectrometer | 2 (bm23 + the LCLS-MFX/ISS catalog precedent) | graduated |
| FlowController | 2 (id32, bm23) | graduated |
| PseudoAxis | 2 (id28, id32) | graduated |
| Goniometer (?) | 2 (id28, id32) | graduated (id28 binding confirm vs LinearStage, SAMPLE-1; id32 4-circle DiffE4CH) |
| RotaryStage | 2 (id19, id16b) | graduated |
| Filter | 2 (id19, id06) | graduated |
| SpectrometerArm | 1 beamline, 2 arms (id32 RIXS + XES) | loose (RIXS-1); grating-dispersive lineage |
| GratingMonochromator | 1 (id32) | graduated |
| Magnet | 1 (id32) | loose (MAG-1) |
| PolarizationAnalyzer | 1 (id32) | loose (POL-2) |
| EnergyAnalyzer | 1 (id28) | loose (ANALYZER-1); crystal-analyzer lineage |
| BeamPositionMonitor | 1 (id28) | loose (DIAG-1) |
| Controller / MonoFeedback (?) | 2 (id06, bm23) | Role not Family; MOCO beam-stabilization (fleet-wide MonoFeedback watch) |
| LargeVolumePress | 0 devices (id06 technique) | NOT a family: technique present, NO press device in public source (PRESS-1) |
| (microscope optics) | 1 (id19) | unmapped; tomography objective/scintillator turret, see id19 facts |

Every Family that the eight ESRF beamlines bind to a graduated catalog entry stays graduated; none coins anything. The three bending-magnet beamlines (BM26 / BM25 / BM23) do NOT bind InsertionDevice, so that family's count holds at five. BM23 is the one beamline that adds a less-common graduated family: its Si555 Johann crystal-analyzer XES spectrometer binds `EmissionSpectrometer` (the LCLS-MFX / ISS precedent), a further consumer that reinforces but does not change a graduated family.

!!! note "ID32 reaches the SpectrometerArm rule-of-three on its own, but it stays HELD"
    ID32 instantiates the same `SpectrometerArmsController` class twice (the RIXS arm and the XES arm), so with the SIX soft-RIXS arm the grating-dispersive `SpectrometerArm` family is sighted three times. Per the owner decision recorded in the shipped descriptor it is HELD, not graduated, here (RIXS-1); graduation is a separate gated catalog PR, never a research fold. Critically, this is the **grating-dispersive** lineage and is distinct from ID28's **crystal-analyzer** arm (the loose `EnergyAnalyzer`, ANALYZER-1). The two ESRF inelastic beamlines do NOT stack onto one count.

## Device classes by beamline count

The raw BLISS controller class names seen in source, before mapping to a CORA Family. ESRF classes are largely beamline-specific (each beamline ships its own `id28.controllers.*` / `id32.controllers.*` package), so cross-beamline class-name recurrence is weak; the shared classes are the BLISS-core and IcePAP primitives.

| Source class | Beamlines |
| --- | --- |
| `Lima` | 8 (id19, id16b, id28, id32, id06, bm26, bm25, bm23) |
| `IcePAP` | 7 (id19, id16b, id28, id32, id06, bm26, bm23; NOT bm25 partial config) |
| `CT2` (P201) | 6 (id28, id32, id06, bm26, bm25, bm23) |
| `ESRF_Undulator` | 5 (id19, id16b, id28, id32, id06; NOT bm26/bm25/bm23 bending magnet) |
| `FalconX` | 3 (id19 per its facts, bm25, bm23); fluorescence MCA |
| `musst` | 5 (id28, id32, id06, bm26, bm23) |
| `TangoShutter` | 5+ (id28, id32, id06, bm26, bm23 confirmed; id19 records it in handles) |
| `slits` | 5+ (id28, id32, id06, bm26, bm23 confirmed; id19/id16b use slit calc, class not recorded in older facts) |
| `Nanodac` | 4 (id28, id06, bm26, bm23) |
| `EBV` | 4 (id28, id32, bm26, bm23) |
| `Moco` | 2 (id06, bm23) |
| `EMH` | 1 (bm23, electrometer) |
| `Mcce` | 1 (bm23, current amplifier) |
| `Spectrometer` (Johann XES) | 1 (bm23, Si555) |
| `BM23Mono` | 1 (bm23) |
| `KbController` | 1 (bm23) |
| `BM23robot` | 1 (bm23) |
| `LakeShore336` | 2 (id32, bm23) |
| `Eurotherm2000` | 1 (bm25) |
| `Monochromator` (BLISS core class) | 2 (bm26 Si111, bm23 via BM23Mono subclass); other ESRF monos use beamline-specific classes (id06 ID06mono, id32 MonochromatorGrating) |
| `PM600` | 1 (bm26) |
| `LinkamHardwareController` | 1 (bm26) |
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

The classes that recur across distinct beamlines AND are not yet a catalog Family. Across the complete eight-beamline public-config ESRF set, **nothing clears the rule-of-three that is not already graduated or already held under an owner decision.** The three CRG / XAS bending-magnet beamlines (BM26 / BM25 / BM23) add only further consumers of already-graduated families (BM23 notably reinforcing the less-common `EmissionSpectrometer` with its Si555 Johann XES spectrometer, and bringing `FlowController` to a second consumer); none surfaces a new graduation candidate. Watches:

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

## Set complete: the standing ESRF verdict

This recurrence now covers the complete public-config ESRF set: eight beamlines (ID19, ID16B, ID28, ID32, ID06, BM26, BM25, BM23). The cross-fleet conclusion is that **the ESRF set, mined as data, earns CORA no new catalog Family.** Every device class either binds an already-graduated Family (the bulk: Monochromator, Slit, Shutter, Camera, LinearStage, Mirror, InsertionDevice, TemperatureController, FluxMonitor, Transfocator, FlowController, EnergyDispersiveSpectrometer, EmissionSpectrometer, GratingMonochromator) or a loose family already held under a cross-facility review or owner decision (SpectrometerArm/RIXS-1, EnergyAnalyzer/ANALYZER-1, Magnet/MAG-1, PolarizationAnalyzer/POL-2, BeamPositionMonitor/DIAG-1, StorageRing/MACHINE-1). The ESRF's distinct value to CORA is therefore NOT catalog enrichment but two other things: (1) the control plane (the first live BLISS / Tango / IcePAP floor across many beamlines, validating that the ControlPort opaque-edge-handle model holds at facility scale), and (2) three open questions worth carrying to staff or a modeling pass: the `EnergyAnalyzer`-vs-`SpectrometerArm` inelastic-arm disambiguation (ID28 vs ID32), the `LargeVolumePress` technique-without-a-device (ID06, PRESS-1), and the firewalled DEG DFXM stack (ID06, DEG-1). Two beamlines need a source caveat carried forward: BM25 (partial public config) and BM23 (2022 stale snapshot).
