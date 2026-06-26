# Sample

*The sample side, and the home of the new `PressureCell` family. The diamond anvil cell sits in the beam under extreme pressure and double-sided laser heating, a sample environment with no fleet analog. Scaffold; devices reverse-engineered from the GSECARS EPICS support tree (iocBoot startup scripts, CARSApp Db templates, the adl MEDM screens), so the device-to-PV reconstruction is rougher than a dodal/BITS roster and carried at medium confidence (CTRL-1).*

The 13-ID-D sample side is the one place in this deployment where CORA coins a new device class. The diffraction spine, the optics, the detectors, all of it reuses existing catalog and loose [Families](../../../catalog/families.md). What forces a new Family is the high-pressure sample environment itself: a diamond anvil cell (DAC) holding the specimen under extreme pressure while two fibre lasers heat it from both sides and in-situ spectroscopy reads back its pressure and temperature. The fleet has nothing like it, so it earns one new loose Family, `PressureCell`, held at a single sighting (HP-1, PRESSURE-1).

## The sample stack (13-ID-D)

| Device | Family | PV / controller | Design note |
| --- | --- | --- | --- |
| `PressureCell` | `PressureCell` (loose, new) | GE/Druck PACE5000 on `13IDD_PACE5000:PC1:Setpoint` / `Pressure_RBV` | the diamond anvil cell; one Asset presenting the `Regulator` Role for its membrane gas pressure, with heating and metrology as capabilities (HP-1, PRESSURE-1) |
| `SampleStage` | `Goniometer` | Galil `m1`-`m4` (X / Z / Y / Omega) + Newport XPS-16 trajectory | DAC positioning stage / micro-diffractometer; single Omega, the Galil-vs-XPS choice a setting (SAMPLE-1) |
| `SampleTable` | `Table` | (DAC lift table) | the table the cell sits on (SAMPLE-1) |
| `MetrologySpectrometer` | `Camera` | LightField PIMAX / PIXIS on `13IDDLF1:` | the cell's pressure / temperature metrology detector (HP-1) |

## The diamond anvil cell: one Asset, three capabilities

`PressureCell` is the diamond anvil cell, and it is **one Asset**, not a cluster of separate devices. It presents the `Regulator` Role for the one thing it actively controls: the membrane gas pressure that drives the anvils together. That pressure is commanded and read back on the GE/Druck PACE5000 controller (`13IDD_PACE5000:PC1:Setpoint`, `13IDD_PACE5000:PC1:Pressure_RBV`). Everything else the cell does is modelled as a **capability of that one Asset**, not as a separate Family:

- **Double-sided laser heating.** Two IPG YLR fibre lasers heat the sample from upstream and downstream (`13IDD:Laser1`, `13IDD:Laser2`), with commanded power on `13IDD:US_LaserPower` and `13IDD:DS_LaserPower`, balanced for symmetric double-sided heating (HEAT-1).
- **In-situ pressure and temperature metrology.** Temperature is inferred from thermal-emission spectroradiometry (`13IDD:us_las_temp`, `13IDD:ds_las_temp`); pressure is read from ruby fluorescence, Raman, and Brillouin spectroscopy. The detector for this metrology is the `MetrologySpectrometer` below (HP-1).

Modelling the heating and the metrology as capabilities of the cell, rather than as their own Families, keeps the high-pressure sample environment as a single coherent Asset: one thing you load, pressurise, heat, and read back, presenting one Role for the one quantity it regulates.

## Why a new Family, and why named `PressureCell`

The naming-r3 choice is deliberate. The bare regime-generic role-noun `PressureCell` was chosen over two tempting alternatives:

- **not `HighPressureCell`**, because that qualifier names the regime (high pressure) rather than the thing, and the regime belongs at the Plan level, not in the device class name; and
- **not `DiamondAnvilCell`**, because that qualifier names the mechanism (the diamond anvils) and so over-specifies. The bare role-noun spans the diamond anvil cell here, large-volume presses, and clamp cells alike.

The Family is held at **n=1**, a single sighting at 13-ID-D, and graduates into the catalog only at a rule-of-three: the HPCAT 16-ID cells, the 13-BM-D large-volume press, and the 4-ID cell are the candidate second and third sightings (HP-1, PRESSURE-1).

## Why the heating lasers do not bind the loose `Laser` family

The two IPG YLR fibre lasers heat the sample, and there is already a loose `Laser` family in the fleet (it appears in the POLAR / 4-ID work). They are **not** the same Role. The `Laser` family covers pump-probe excitation, a fundamentally different job from steady-state sample heating. More to the point, the heating here is **open-loop on commanded power**: CORA commands `13IDD:US_LaserPower` / `13IDD:DS_LaserPower` and the sample temperature is *inferred* from thermal emission, not held by a closed temperature loop. So the live heating is a power actuator, a capability of the cell, not a temperature `Regulator` and not a binding of the pump-probe `Laser` family (HEAT-1). No closed-loop temperature controller is invented here.

## The DAC positioning stage and the metrology spectrometer

`SampleStage` is the DAC positioning stage, the micro-diffractometer that places the cell in the beam. It binds the catalog `Goniometer` Family, the same Family the i03 Smargon uses: a single Omega rotation with translation axes, here driven by Galil controllers (`m1`-`m4`: X, Z, Y, Omega) with a Newport XPS-16 for trajectory scanning. Which controller drives a given move, Galil versus XPS, is a per-Asset setting, not a separate device class (SAMPLE-1). The DAC lift table the cell rides on binds the catalog `Table` Family (SAMPLE-1).

`MetrologySpectrometer` is the cell's pressure / temperature metrology detector, a LightField PIMAX / PIXIS on `13IDDLF1:`. It binds the catalog `Camera` Family. It is reuse, not novelty: a spectroscopic camera reading ruby fluorescence, Raman, and the thermal-emission spectra that feed the cell's metrology capability (HP-1).

## Why a new family here, but only one

The high-pressure sample environment has no fleet analog, so it earns the one new loose Family, `PressureCell`. Everything around it reuses what the catalog already carries: the XRD spine (source, monochromator, mirrors, slits, aperture, attenuator) all binds existing Families, the area detectors and flux monitors and the Dante MCA are the established detection shapes, and the positioning stage and metrology camera reuse `Goniometer` and `Camera`. The novelty is localised entirely to the sample environment, and even there it is one Asset with capabilities, not a sprawl of new classes. The Koyo laser-safety PLC that gates emission is modelled as an Enclosure permit axis on the [governance](../../aps/index.md#the-safety-envelope) side, not as a device (LASER-1, PSS-1).

See [Open questions](../questions.md) for the sample-side facts still to confirm, [Inventory](../inventory.md) for the Asset tree, [Model](../model.md) for the loose-Family graduation plan, and [the source walk](../beamline.md) for the device-to-PV reconstruction.
