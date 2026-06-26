# Techniques

*What the modelled part of 13-ID-D is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../aps/index.md#the-techniques-adapted-here) is how a facility adapts it. 13-ID-D runs monochromatic X-ray diffraction on a sample held in a diamond anvil cell under extreme pressure and double-sided laser heating: high-pressure powder diffraction and high-pressure single-crystal diffraction. Both reuse Methods that the fleet already carries (or has pending), so the slugs below render unlinked and are carried pending until one enters scope (TECH-1). Nothing here coins a new technique. The novelty at 13-ID-D is the sample environment, not the measurement.

## High pressure is a sample environment, not a technique

The diamond anvil cell squeezes the sample between two anvils and heats it from both sides, so the diffraction is measured at extreme pressure and temperature rather than at ambient conditions. That is a difference in the conditions the sample sits in, not a difference in what the beam measures or how the pattern is read. A powder ring is a powder ring whether the powder is at ambient pressure or inside a cell; a single-crystal reflection is a single-crystal reflection either way.

So high pressure binds the same Methods as ordinary diffraction, carried as a Plan-level sample-environment difference. This follows the [4-ID precedent](../4-id/techniques.md), where high-pressure diffraction is the same `diffraction` Method run with a pressure cell, a Plan setting over the same measurement and not a new slug. The cell, its heating, and its in-situ pressure and temperature metrology are modelled as equipment (the new [PressureCell](equipment/sample.md) family and its capabilities), and the conditions they impose are expressed in the Plan, not in the technique name.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| High-pressure powder diffraction | `powder_diffraction` | monochromatic powder rings from the cell, recorded on the [area detector](equipment/detector.md); shares the i11 powder Capability; high pressure is a Plan-level sample-environment setting, pending (TECH-1) |
| High-pressure single-crystal diffraction | `diffraction` | reciprocal-space reflections from a single crystal in the cell on the [area detector](equipment/detector.md), oriented on the [diffractometer stage](equipment/sample.md); shares the 4-ID / 8-ID / CSX / i19 diffraction Capability; high pressure is a Plan-level sample-environment setting, pending (TECH-1) |

Both techniques need the [incident beam chain](beamline.md) (the shared 13-ID-A monochromator, the K-B focusing mirror, the beam-defining and clean-up apertures, and the attenuator filter bank), the [pressure cell and its diffractometer stage](equipment/sample.md), the [area detector on its 2theta arm](equipment/detector.md), and the ion-chamber and photodiode [flux monitors](equipment/detector.md) for normalization. The diffraction spine is entirely catalog reuse; see [Model](model.md) for why nothing in the measurement path graduates.

## What the cell lets the science do

The diamond anvil cell is what makes 13-ID-D distinct. It lets the experiment probe matter at extreme pressure and temperature, conditions that reach toward planetary interiors and that no other deployment in the fleet has reached. The science is to watch how a material's structure responds as it is squeezed and heated: phase transitions, equations of state, and structural changes under pressure and temperature that do not appear at ambient conditions.

Two cell capabilities do the work, and both are modelled as capabilities of the single [PressureCell](equipment/sample.md) Asset rather than as separate families:

- **Pressure.** The cell presents the Regulator Role for its membrane gas pressure, driven through the PACE5000 membrane controller. Setting and reading the membrane pressure is the actuated handle on the squeeze (PRESSURE-1, HP-1).
- **Double-sided laser heating.** Two IPG YLR fibre lasers heat the sample from both sides, balanced, so the heated volume is hot through its thickness rather than only on one face (HEAT-1). The live heating is open-loop on commanded laser power: there is no closed-loop temperature Regulator today, the lasers are a power actuator and the temperature is inferred from the sample's own thermal emission (HEAT-1).

These two together open the pressure-temperature space that the diffraction then samples. The cell sets the conditions; the diffraction reads the structure.

## The in-situ metrology is part of the cell

Knowing the pressure and temperature at the sample is itself measured in situ, and that metrology belongs to the cell as a capability, not to a technique:

- **Temperature** is read from thermal-emission spectroradiometry: the sample's own glow, dispersed and fit to a thermal spectrum, gives the temperature on each side (HEAT-1, HP-1). The spectrometer that records it binds the catalog [Camera](equipment/detector.md) family (LightField PIMAX / PIXIS), the cell's pressure-and-temperature metrology detector.
- **Pressure** is read from ruby fluorescence, Raman, or Brillouin measurements on the cell (PRESSURE-1, HP-1). These calibrate the pressure that the membrane controller commands against an in-situ standard.

This metrology is not a separate Method. It is how the cell knows the conditions it is imposing, the same way a temperature controller knows its setpoint. It is modelled as part of the PressureCell capability and its [metrology spectrometer](equipment/detector.md), and it does not appear in the technique table above.

## Not modelled yet

The concrete acquisition recipes are not written yet: the powder and single-crystal scan sequences, the laser-power ramp and balancing during heating, the ruby / Raman / Brillouin pressure-calibration steps, and how a Plan threads the pressure and temperature setpoints through a diffraction run. They join as the deployment approaches the point where CORA conducts over the floor.

Whether `powder_diffraction` and `diffraction` enter CORA's catalog, and who owns them across the facilities that share them, is an owner-scope decision and is deferred (TECH-1); minting a cross-facility Method is not done from a modelling exercise until a technique enters a real scope. The Practices are carried pending on the [APS Site](../aps/index.md#the-techniques-adapted-here): `13IDD_powder_diffraction_practice` (`powder_diffraction`) and `13IDD_diffraction_practice` (`diffraction`), both pending TECH-1.

The 2theta swing transform that would bind a `PseudoAxis` on the [detector arm](equipment/detector.md) is deferred, not invented: the arm's prefix was seen only in a controller test template, so the binding is left open (DET-1). A closed-loop temperature Regulator for the heating is likewise not modelled, because today's heating is open-loop on commanded power (HEAT-1). See [Open questions](questions.md) for the world-facts to confirm first, and [Model](model.md) for why the PressureCell family is held at one Asset until a rule-of-three graduates it (HP-1).
