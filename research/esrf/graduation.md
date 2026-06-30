# Catalog graduation decisions: ESRF

Step 2 of the roadmap (survey -> recurrence -> graduation): take the recurring candidates from
`recurrence.md` through an intentional graduate / model-as-Assembly / fold / leave-loose
decision, with the naming-r3 gate applied to every name a future graduation would use. The
authority for "graduated" is `catalog/catalog.yaml`, not this page; where they disagree, the
catalog wins.

## The honest outcome: no new Family earned by the ESRF pass

The ESRF passes (id19, id16b, id28, id32, id06, bm26, bm25, bm23, the complete public-config set)
reuse already-graduated catalog vocabulary almost entirely; `recurrence.md` shows every recurring
class already `graduated`. The point of the ESRF deployments was the control plane (the first live
BLISS / Tango floor), not new device families, so the device families are held constant while one
axis (the floor) moves. The three bending-magnet additions (bm26, bm25, bm23) coin nothing: each
is a further consumer of already-graduated families (bm23 reinforces EmissionSpectrometer with its
Si555 Johann crystal arm). The one substantive step-2 finding is a loose-family **disambiguation**,
not a graduation.

## Decisions

| Candidate | Distinct beamlines | CORA status (per catalog) | Decision | naming-r3 |
| --- | --- | --- | --- | --- |
| Camera | 8 (all) | GRADUATED | reinforce only | passes |
| Slit, Shutter, LinearStage | 7 each | GRADUATED | reinforce only | passes |
| Monochromator | 6 | GRADUATED | reinforce | passes |
| TemperatureController | 6 (id28, id32, id06, bm26, bm25, bm23) | GRADUATED (presents Regulator) | reinforce | passes |
| FluxMonitor | 5 (id16b, id28, id06, bm26, bm23) | GRADUATED | reinforce | passes |
| InsertionDevice | 5 (id19, id16b, id28, id32, id06) | GRADUATED | reinforce; NOT bm26/bm25/bm23 (bending magnet, source held loose) | passes |
| EnergyDispersiveSpectrometer | 3 (id16b, bm25, bm23) | GRADUATED | reinforce | passes |
| Transfocator | 3 (id19, id28, id06) | GRADUATED | reinforce (rule-of-three across the fleet) | passes |
| EmissionSpectrometer | bm23 (+ LCLS-MFX / ISS precedent) | GRADUATED | reinforce; the BM23 Si555 Johann crystal arm | passes |
| FlowController | 2 (id32, bm23) | GRADUATED | reinforce | passes |
| GratingMonochromator | id32 | GRADUATED | reinforce | passes |
| EnergyAnalyzer | id28 | LOOSE (not in catalog, `ANALYZER-1`) | hold; the IXS crystal-analyzer arm (`tth_multilayer` + `inca`) | spelled-out form passes |
| SpectrometerArm | id32 (RIXS + XES arms) | LOOSE (not in catalog, `RIXS-1`) | hold; rule-of-three is met on id32 alone + the SIX precedent, but held per owner decision | passes |
| Magnet | id32 (+ 4-ID, i10-1 per shipped descriptors) | LOOSE (`MAG-1`) | hold; do not coin from id32 | passes (bare thing-noun) |
| StorageRing | 5 (id28, id32, id06, bm26, bm23) | LOOSE (`MACHINE-1`) | hold; the ESRF machine status object | passes |

## The substantive finding: ID28 and ID32 reinforce DIFFERENT loose families

The two ESRF inelastic-scattering beamlines look like they reinforce the same loose family but do
not, and this is the recurrence-relevant call:

- **ID28 (IXS)** carries a *crystal* analyzer arm: `tth_multilayer` (TwoThetaMultilayer) carrying
  `inca` inclined-crystal analyzers in backscattering. Per `catalog/catalog.yaml` this is the
  loose **`EnergyAnalyzer`** lineage (`ANALYZER-1`, "IXS diced-crystal analyzer selecting a fixed
  final energy").
- **ID32 (RIXS / XMCD)** carries *grating-dispersive* Rowland arms: `rixs_spectro` + `xes_spectro`
  (both `SpectrometerArmsController`, grating modes, Rowland radius). This is the loose
  **`SpectrometerArm`** lineage (`RIXS-1`, "grating-dispersive multi-chamber RIXS arm").

So they are NOT the same data point toward one graduation; they are sightings toward two distinct
loose families. Neither is coined from ESRF alone.

Open discrepancy carried honestly: the shipped `deployments/id28/beamline.yaml` binds the ID28
arm to `SpectrometerArm`, whereas the catalog note assigns the IXS crystal arm to
`EnergyAnalyzer`. Recorded as a question for the next ID28 modeling pass (which loose family ID28
reinforces), not silently aligned. Either way it stays LOOSE and held.

## Recurring loose-family / DIAG notes

- **BeamPositionMonitor (DIAG-1).** The ID28 OH2 Elettra quadrant monitor binds the loose
  `BeamPositionMonitor`, held under the fleet-wide `DIAG-1` position-monitor review; do not coin.
- **TimingController watch.** The ID28 MUSST gated-acquisition card may present the graduated
  `TimingController`; confirm vs a bare GenericProbe. MUSST / PandABox / Zebra-style timing recurs
  fleet-wide (the NSLS-II SRX Zebra watch), a graduation-reinforcement confirmation, not a new coin.

## Scope and provenance

Covers the complete public-config ESRF set, eight beamlines (id19, id16b, id28, id32, id06, bm26,
bm25, bm23); id28 and id32 are shipped deployments given retrospective Tier-2 passes, so their
facts cross-check the shipped descriptors. Counts are distinct physical beamlines; see
`recurrence.md` for the per-class table and the per-beamline `facts.md` for the analyzer-arm
disambiguation detail.
