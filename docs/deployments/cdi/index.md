# CDI

*Coherent diffraction imaging at NSLS-II, beamline 9-ID: a forward-CDI, ptychography, and Bragg-CDI beamline that focuses a coherent beam with a KB mirror pair and records the far-field diffraction pattern on photon-counting area detectors. This page describes how CORA would model and run CDI; the model is reverse-engineered from public configuration, not yet confirmed by CDI staff.*

| Property | Value |
| --- | --- |
| Asset | `CDI` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 9` (PV namespace `XF:09ID*`) |
| Institution | Brookhaven National Laboratory (context; not modeled as an Asset or Facility) |
| Status | Reverse-engineered from public config (design-phase scaffold) |
| Source | IVU18 in-vacuum undulator (`SR:C09-ID:G1{IVU18:1}`) |

!!! note "How CORA would land on CDI"
    This is NSLS-II 9-ID. CORA also models APS [9-ID](../9-id/index.md), a different beamline at a different facility; CDI lives at `XF:09ID*`. These pages describe how CORA would model, govern, and conduct CDI, joining the NSLS-II coherent siblings [CHX](../chx/index.md) and [CSX](../csx/index.md) and the ptychography-capable nanoprobe [HXN](../hxn/index.md). They are not a survey of the beamline's current software. The hardware facts (devices, EPICS PVs, axes) are read from public NSLS-II open source (the [`NSLS2/cdi-profile-collection`](https://github.com/NSLS2/cdi-profile-collection) profile collection and the [`NSLS2/cditools`](https://github.com/NSLS2/cditools) device library) and verified against them; vendor part numbers and physical positions are not in them, so they, and every read value, are carried `confirm` until CDI staff verify them ([Open questions](questions.md)). This is a design-phase scaffold: the descriptor and these docs, with scenarios deferred.

## The defining shape: coherent imaging

**Coherent diffractive imaging** arrived in the fleet with Diamond [i13-1](../i13-1/index.md) (ptychography and CDI, a deliberately partial endstation), which opened the deferred coherent-imaging Method. CDI is the second coherent-diffractive-imaging deployment, the first at NSLS-II, and the first modelled as a full source-to-detector beamline: it focuses a coherent beam to a small spot, records the far-field diffraction pattern on a photon-counting area detector, and recovers the real-space image offline by phase retrieval. The fleet has met coherence in other acts too: APS [8-ID](../8-id/index.md) and [CHX](../chx/index.md) record correlation time series (XPCS), [CSX](../csx/index.md) records coherent soft X-ray scattering, and [HXN](../hxn/index.md) runs ptychography as one of several scanning-probe modes.

The value to CORA is reinforcement, not new vocabulary. The coherent area detector that records the diffraction pattern is the same `Camera` shape CHX and HXN already carry; the KB nanofocus that forms the coherent spot is the same `Mirror` shape FMX and SRX carry; the offline reconstruction is a `ComputePort` leg, the imaging analogue of CHX's correlation analysis, not a beamline Method. CDI introduces **no new catalog Family**, and its techniques reinforce the deferred coherent-imaging Method i13-1 opened (the pending `ptychography` Method) without coining anything new.

The three imaging techniques differ only in how the frames are taken: a single far-field frame (forward CDI), a scan of overlapping frames across the sample (ptychography), or a rocking series around a Bragg peak (Bragg CDI). All three share the KB nanofocus, the goniometer, and the coherent detectors.

## The beamline

Along the beam, in order:

- [Source](beamline.md): the IVU18 in-vacuum undulator and the first-optics hutch (`9-ID-A`), rendered as the generated source-stage device walk: the silicon double-crystal monochromator and the double-multilayer monochromator, the vertical and horizontal pre-mirrors, the white-beam and branch slits, the attenuator foils, the master energy, and the upstream beam diagnostics.
- [Sample](equipment/sample.md): the KB nanofocusing mirror pair that forms the coherent spot, the beam-conditioning unit that trims it just before the sample, the sample goniometer, the endstation positioning towers, and the endstation diagnostic cameras.
- [Detector](equipment/detector.md): the Eiger2 and Merlin photon-counting area detectors that record the far-field coherent-diffraction pattern.

Cutting across all three:

- [Controls](equipment/controls.md): the motion controllers and the timing seam. Unlike the other NSLS-II coherent beamlines, the CDI profile collection exposes no hardware trigger box, which is the headline controls question.

The cross-cutting reference view is the [Inventory](inventory.md).

## Techniques

[Techniques](techniques.md): the coherent-imaging techniques CDI runs (forward CDI, ptychography, Bragg CDI), each a [Catalog](../../catalog/methods.md) Method, and why their Methods stay deferred (the 8-ID / CHX / HXN owner-scope cohort).

## Governance

[Governance](governance.md): who may act at CDI and the trust shape CORA applies; CORA brings its own per-Actor authority.

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's CDI content lives.
