# Sample

*The MD3 microdiffractometer goniometer, the sample environment, and the ISARA robot. PVs / interfaces verified against `mx3_beamline_library/devices/{motors,cryo}.py` and `classes/motors.py`.*

MX3 holds a cryocooled crystal on the MD3 microdiffractometer and rotates it through an oscillation; the sample side is the goniometer, its cooling and viewing, and the robot that loads it.

| Asset | Family | PV / interface | What it does |
| --- | --- | --- | --- |
| `Goniometer` | Goniometer | MXCuBE Exporter (no PV) | orients the crystal (omega / kappa / phi) |
| `SampleTemperature` | TemperatureController | `MX3CRYOJET01:` | cryojet sample cooling |
| `Backlight` | Backlight (loose) | MD3 Exporter (no PV) | sample backlight for centring |
| `BeamStop` | BeamStop | MD3 Exporter (no PV) | blocks the direct beam at the sample |

## The MD3 goniometer

The `Goniometer` is the MD3 (Arinax) microdiffractometer: omega rotation plus a mini-kappa (kappa / phi), sample centring (CentringX / Y), and alignment (AlignmentX / Y / Z). It reuses the graduated `Goniometer` family, the same one Diamond [I03](../../i03/index.md) earned from its Smargon (MX3's MD3 is a richer instance, kappa plus alignment). The discriminator the family carries, a multi-axis crystal-orientation goniometer, fits exactly.

What is new is not the family but the **control interface**: the MD3 is driven over the MXCuBE Exporter protocol (a custom TCP framing), not EPICS, so it carries no PV; each axis is an Exporter property name (`Omega`, `CentringX`, ...) resolved at runtime against the MD3 host. CORA models it as a `Goniometer` Asset and treats the Exporter as a `ControlPort` adapter; the concrete host is deployment config (GONIO-1). The MD3 also carries the `Backlight` and `BeamStop` as Exporter sub-devices.

## Sample environment

The `SampleTemperature` cryojet reuses the `TemperatureController` family (graduated in #350), keeping the crystal at cryogenic temperature through the dataset.

## The ISARA robot

MX3's throughput comes from the ISARA sample-mounting robot, which loads pins from a dewar onto the goniometer between datasets, its mount / unmount trajectories gated on the MD3 state. It is **not** modelled as a device here: CORA models autonomous sample exchange as a Procedure over the spine, threaded through the `Subject` aggregate so each crystal's identity and provenance is tracked and gated by a Clearance, the same shape as the Diamond i03 and i24 loops (ROBOT-1). The robot's TCP interface is named, but the Procedure is deferred at this design phase.
