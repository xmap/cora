# Techniques

*What I11 is designed to do, as intent. Design-phase.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../diamond/index.md) is how a facility adapts it. I11 does high-resolution powder diffraction, a new science domain for CORA. Which Methods enter scope is an open question (TECH-1).

| Technique | Beam | Detector | Status in CORA |
| --- | --- | --- | --- |
| High-resolution powder diffraction | monochromatic (DCM) | `Mythen3` strip detector on the two-theta arm, capillary `Spinner` for averaging | new Capability, pending (TECH-1) |
| Variable-temperature powder diffraction | monochromatic | same, over a temperature ramp on the thermal actuators | the variable-temperature axis that earns TemperatureController (TEMP-1) |
| Autonomous sample exchange | n/a | n/a | a Procedure over the spine + a Subject custody thread, pending (ROBOT-1) |

A few points of intent shape the model:

- **Powder diffraction is a new Capability, not a new device shape.** A measurement spins a capillary sample for powder averaging and sweeps the detector arm while the Mythen3 strip captures the diffraction pattern. The device Roles already exist (the diffractometer and spinner present Positioner, the Mythen3 presents Detector); what is new is the science Capability binding them (TECH-1).
- **Variable temperature is the genuinely new operating axis, and it earns an abstraction.** Powder diffraction at I11 routinely runs over a temperature ramp using the Cyberstar/Eurotherm blowers and the cryostreams. These are continuous-setpoint actuators (`set(value)`/`ramprate`), the first such cluster CORA has at rule-of-three. That earns the `TemperatureController` Family graduation and a settable-actuator Role, routed to gate-review (TEMP-1).
- **The diffractometer is not goniometry.** Unlike I03's MX goniometer (a sample-orientation cradle, the graduated Goniometer Family), I11's theta/two_theta/delta are a sample rotation plus detector-arm angles, modelled as per-axis RotaryStage (GONIO-1).

The concrete recipes (two-theta ranges, exposure, temperature ramps) are calibration the deployment must supply. See [Open questions](questions.md).
