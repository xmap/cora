# Sample

*The Arinax MD3 microdiffractometer goniometer, the sample environment, and the ISARA robot. Interfaces read from the `light911/NSRRC_TPS07A` control tree; the EPICS PV namespace (`07a-ES:`) is verified but per-axis records are pending.*

TPS 07A holds a cryocooled crystal on the MD3 microdiffractometer and rotates it through an oscillation; the sample side is the goniometer, its cooling, and the robot that loads it.

| Asset | Family | PV / interface | What it does |
| --- | --- | --- | --- |
| `Goniometer` | Goniometer | EPICS via DHS (`07a-ES:`, records pending) | orients the crystal (omega / kappa / phi) |
| `SampleTemperature` | TemperatureController | EPICS (PV pending) | cryostream sample cooling |
| `BeamStop` | BeamStop | EPICS (PV pending) | blocks the direct beam at the sample |

## The MD3 goniometer

The `Goniometer` is the Arinax MD3 microdiffractometer: omega rotation plus a mini-kappa (kappa / phi), sample centring (CentringX / Y), and alignment (AlignmentX / Y / Z). It reuses the graduated `Goniometer` family, the same one Diamond [I03](../../i03/index.md) earned from its Smargon and the Australian Synchrotron [MX3](../../mx3/equipment/sample.md) reused for its MD3. The discriminator the family carries, a multi-axis crystal-orientation goniometer, fits exactly.

The contrast with MX3 is the **control interface, not the device**. MX3 drives its MD3 over the MXCuBE Exporter protocol (a separate TCP transport, no PV); TPS 07A reaches its MD3 as **EPICS PVs through the Device Handler Server**, so it is on the EPICS floor like every other 07A device. The DCSS server orchestrates the oscillation *above* that floor (the seam CORA replaces, see [Controls](controls.md)). CORA models it as a `Goniometer` Asset; the endstation PV records (`07a-ES:` namespace) are pending (GONIO-1).

## Sample environment

The `SampleTemperature` cryostream reuses the `TemperatureController` family (graduated in #350), keeping the crystal at cryogenic temperature through the dataset. The vendor and PV are pending (ENV-1).

## The ISARA robot

TPS 07A's throughput comes from the ISARA sample-mounting robot, which loads pins from a dewar onto the goniometer between datasets. It is **not** modelled as a device here: CORA models autonomous sample exchange as a Procedure over the spine, threaded through the `Subject` aggregate so each crystal's identity and provenance is tracked and gated by a Clearance, the same shape as the Diamond i03, i24, and MX3 loops (ROBOT-1). The robot's interface is named, but the Procedure is deferred at this design phase.
