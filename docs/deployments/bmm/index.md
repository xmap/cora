# BMM

*X-ray absorption spectroscopy at NSLS-II, beamline 6-BM: transmission and fluorescence XAS / EXAFS. This page describes how CORA would model and run BMM; the model is reverse-engineered from public configuration, not yet confirmed by BMM staff.*

| Property | Value |
| --- | --- |
| Asset | `BMM` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 6` (PV namespace `XF:06BM*`) |
| Institution | Brookhaven National Laboratory (context; not modeled as an Asset or Facility) |
| Status | Reverse-engineered from public config (design-phase scaffold) |
| Source | 6-BM bending magnet (`SR:C06`) |

!!! note "How CORA would land on BMM"
    These pages describe how CORA would model, govern, and conduct BMM, the third NSLS-II beamline after [FXI](../fxi/index.md) and [HXN](../hxn/index.md). They are not a survey of the beamline's current software. The hardware facts (devices, EPICS PVs, axes) are read from public NSLS-II open source (the [`NSLS2/bmm-profile-collection`](https://github.com/NSLS2/bmm-profile-collection) profile collection) and verified against it; vendor part numbers and physical positions are not in it, so they, and every read value, are carried `confirm` until BMM staff verify them ([Open questions](questions.md)). This is a design-phase scaffold: the descriptor and these docs, with scenarios deferred.

## The defining shape: an energy scan

Every prior CORA deployment measures by scanning **position** ([FXI](../fxi/index.md) full-field at a fixed energy, [HXN](../hxn/index.md) rastering a spot, 2-BM rotating a sample). BMM measures by scanning **energy**: it sweeps the monochromator across an element's absorption edge and records the incident, transmitted, and reference ion-chamber currents (and a fluorescence spectrum) at each energy point. The absorption, `ln(I0/It)` versus energy, *is* the data. This is the spectroscopy axis CORA has not had, and BMM is the first real consumer of the `energy_scan` Capability the catalog already anticipates (see [Techniques](techniques.md)).

## The beamline

Along the beam, in order:

- [Source](beamline.md): the bending-magnet source and the optics hutch (`6-BM-A`), rendered as the generated source-stage device walk: two mirrors, the double-crystal monochromator, the beam-defining slits, and the attenuating filters.
- [Sample](equipment/sample.md): the endstation XAFS stages, the sample positioning table, the rotating sample wheel for batch scans, and the reference-foil holder.
- [Detector](equipment/detector.md): the XAS detectors read at each energy point, the ion chambers (transmission) and the energy-dispersive detector (fluorescence).

Cutting across all three:

- [Controls](equipment/controls.md): the conducting engine that sweeps the energy and reads the detectors per point, and the motion controllers.

The cross-cutting reference view is the [Inventory](inventory.md).

## Techniques

[Techniques](techniques.md): what BMM would run (transmission XAS, fluorescence XAS, EXAFS), and the open question of the `energy_scan` Capability, bound through an NSLS-II [Practice](../nsls2/index.md#the-techniques-adapted-here).

## Governance

[Governance](governance.md): who may act at BMM and the trust shape CORA applies; CORA brings its own per-Actor authority.

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's BMM content lives.
