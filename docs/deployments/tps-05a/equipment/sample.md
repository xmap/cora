# Sample

*The Arinax MD3 microdiffractometer goniometer, the sample environment, and the ISARA robot. The kit is read from the SPXF facility pages; the control model is inherited from the [TPS 07A](../../tps-07a/equipment/sample.md) reading and the 2025 cluster paper.*

TPS 05A holds a cryocooled crystal on the MD3 microdiffractometer and rotates it through an oscillation; the sample side is the goniometer, its cooling, and the robot that loads it, the same shape as TPS 07A.

| Asset | Family | PV / interface | What it does |
| --- | --- | --- | --- |
| `Goniometer` | Goniometer | EPICS via DHS (`05a-ES:` inferred, PV-1) | orients the crystal (omega / kappa / phi) |
| `SampleTemperature` | TemperatureController | EPICS (PV pending) | cryostream sample cooling |
| `BeamStop` | BeamStop | EPICS (PV pending) | blocks the direct beam at the sample |

## The MD3 goniometer

The `Goniometer` is the Arinax MD3 microdiffractometer: omega rotation plus a mini-kappa (kappa / phi), sample centring, and alignment. It reuses the graduated `Goniometer` family, the same instance Diamond [I03](../../i03/index.md) earned and that [TPS 07A](../../tps-07a/equipment/sample.md) and [MX3](../../mx3/equipment/sample.md) reuse. As at 07A, it is reached as **EPICS PVs through the Device Handler Server** (on the EPICS floor), with the DCSS server orchestrating the oscillation above that floor (the seam CORA replaces, see [Controls](controls.md)).

The difference from 07A is provenance, not shape: 07A's MD3 PVs were read from its control tree (the `07a-ES:` namespace), while 05A has no dedicated tree, so its endstation namespace (`05a-ES:`) is inferred by cluster convention and the axis PV records are pending (GONIO-1, PV-1).

## Sample environment

The `SampleTemperature` cryostream reuses the `TemperatureController` family (graduated in #350), keeping the crystal at cryogenic temperature through the dataset. The vendor and PV are pending (ENV-1).

## The ISARA robot

TPS 05A's throughput comes from the ISARA sample-mounting robot, the same model 07A runs. It is **not** modelled as a device here: CORA models autonomous sample exchange as a Procedure over the spine, threaded through the `Subject` aggregate so each crystal's identity and provenance is tracked and gated by a Clearance, the same shape as the Diamond i03, i24, 07A, and MX3 loops (ROBOT-1). The Procedure is deferred at this design phase.
