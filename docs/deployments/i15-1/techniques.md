# Techniques

*What I15-1 is designed to do, as intent. Design-phase.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../diamond/index.md) is how a facility adapts it. I15-1 does total scattering / pair distribution function (PDF), a new science domain for CORA. Which Methods enter scope is an open question (TECH-1).

| Technique | Beam | Detector | Status in CORA |
| --- | --- | --- | --- |
| Total scattering / PDF | fixed-energy, bent-Laue mono | `Eiger` (Detector Role), wide-Q on the two-theta arm | new Capability, pending (TECH-1) |
| Autonomous powder/capillary exchange | n/a | n/a | a Procedure over the spine + a Subject custody thread, pending (ROBOT-1) |

A few points of intent shape the model:

- **Total scattering is a new Capability, not a new device shape.** A PDF measurement captures wide-Q scattering on the Eiger across the two-theta arm at a fixed high energy. The device Roles already exist (Camera presents Detector, the mono and arm present Positioner); what is new is the science Capability binding them. Carried pending on the [Diamond Practices](../diamond/index.md) (TECH-1).
- **Energy scanning is explicitly NOT in scope here.** I15-1's bent-Laue monochromator selects a fixed energy: dodal exposes `energy_kev` as a read-only readback derived from the crystal y position via a lookup table, not a commanded or swept axis. So the pending `energy_scan` Capability is **not** earnable from I15-1's source; it must wait for a tunable XAS/EXAFS beamline whose scanning monochromator is actually instantiated in dodal (ENERGY-1).
- **The autonomous loop reuses the I03 shape.** The powder/capillary robot exchange is a Procedure over the spine threaded through the `Subject` aggregate and gated by a Clearance, the same shape as the I03 MX loop, with a powder/capillary twist instead of MX pins (ROBOT-1).

The concrete recipes (q-ranges, exposure, the exchange sequence) are calibration the deployment must supply. See [Open questions](questions.md) for what must be confirmed first.
