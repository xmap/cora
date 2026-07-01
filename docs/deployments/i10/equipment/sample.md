# Sample

*The i10 sample side across both endstations. Scaffold; PVs read from dodal, carried confirm.*

i10 carries two sample sides, one per endstation, fed by the shared twin-APPLE-II and PGM spine through the switching mirror. The i10-rasor endstation (ME01D) holds the diffractometer that orients a crystal in the polarized soft X-ray beam, the polarization-analysis arm that resolves the scattered polarization, a cryostat sample stage, a Lakeshore 340, and a pinhole. The i10-1 / I10J magnet endstation (BL10J) holds the applied-field environment for dichroism: an electromagnet, a superconducting field-sweep magnet, their sample stages, and a Lakeshore 336. Both are modelled flat in the [descriptor](../inventory.md), grouped only when a feature must act on the whole.

Neither side coins a Family here. The diffractometer reuses `Goniometer`, the cryostat stage and the magnet stages reuse `LinearStage`, the Lakeshores reuse the graduated `TemperatureController`, the pinhole reuses `Aperture`, the point detection reuses `FluxMonitor`, and the polarization-analysis arm binds the graduated `PolarizationAnalyzer` (earned across 4-ID / i10 / ID32 / P09, presenting Positioner). The two magnet devices bind the graduated catalog `Magnet` Family: i10-1 was its second sighting after 4-ID, and with the later ESRF ID32 magnet the family reached a rule-of-three and graduated (see [Loose families at a second sighting](#loose-families-at-a-second-sighting)). The genuinely new modelling move at i10, polarization as a driven axis, sits on the source side as a reused `PseudoAxis`, not here (see the generated [Source walk](../beamline.md) and [Model](../model.md)).

## The i10-rasor endstation (ME01D)

RASOR's purpose is magnetic materials by resonant soft X-ray scattering and reflectivity, with the option to resolve the polarization of the scattered beam. The sample circles set the scattering geometry, the analysis arm carries the analyzer crystal, and the cryostat holds the sample in air at low temperature.

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `Diffractometer` | [`Goniometer`](../../../catalog/families.md) | `ME01D-MO-DIFF-01:` | the RASOR sample circles (two-theta scattering arm, sample theta / chi, chamber X, alpha); circle roles and whether they compose an Assembly are pending (DIFF-1) |
| `ReciprocalSpace` | [`PseudoAxis`](../../../catalog/families.md) | (over the circles) | the reciprocal-space axis over the diffractometer circles; the inverse-kinematics rule is deferred (DIFF-2) |
| `AnalyzerArm` | [`PolarizationAnalyzer`](../../../catalog/families.md) (catalog) | `ME01D-MO-POLAN-01:` | the polarization-analysis arm (analyzer two-theta / theta, py / pz, eta); catalog Family, graduated across 4-ID / i10 / ID32 / P09 (POL-2) |
| `DetectorSlit` | [`Slit`](../../../catalog/families.md) | `ME01D-MO-APTR-0` | the RASOR detector-defining slit |
| `Pinhole` | [`Aperture`](../../../catalog/families.md) | `ME01D-EA-PINH-01:` | the sample pinhole (STAGE-1) |
| `SampleStage` | [`LinearStage`](../../../catalog/families.md) | `ME01D-MO-CRYO-01:` | the cryostat sample stage (x / y / z); plain in-air translation, not a UHV `Manipulator` (STAGE-1) |
| `SampleTemperatureController` | [`TemperatureController`](../../../catalog/families.md) | `ME01D-EA-TCTRL-01:` | Lakeshore 340; presents `Regulator` (TEMP-1) |

The diffractometer reuses the catalog `Goniometer`, the Family the rotation-MX and soft X-ray diffraction siblings already earned. Its two-theta scattering arm, sample theta / chi, chamber X, and alpha set the scattering geometry for resonant soft X-ray scattering and reflectivity; the circle roles are carried pending (DIFF-1). The reciprocal-space coordination over those circles is a `PseudoAxis`, a sibling of the energy and polarization axes, with the inverse-kinematics rule deferred exactly as 4-ID, 8-ID, and i06 deferred theirs (DIFF-2). Whether the circles compose an `Assembly(Diffractometer)` is named, not built; the first cut is the flat `Goniometer` Asset plus the reciprocal-space axis (DIFF-1).

The analysis arm binds the catalog `PolarizationAnalyzer`, graduated across 4-ID / i10 / ID32 / P09, presenting Positioner (POL-2). This is a deliberate CORA modelling choice: model RASOR's defining polarization-analysis role on the real motorized arm rather than hide it. dodal exposes the arm's motors only (analyzer two-theta / theta, py / pz, eta); the analyzer crystal is implicit hardware, and no crystal specifics are invented here. The analyzer-crystal spec stays a per-Asset detail to confirm (POL-2).

The cryostat sample stage reuses `LinearStage`. It is a plain in-air translation (x / y / z), not a UHV `Manipulator`, so the conservative first cut binds the simpler Family (STAGE-1). The pinhole reuses `Aperture` (STAGE-1). The Lakeshore 340 reuses the graduated `TemperatureController`, which presents the `Regulator` Role: a settable setpoint with a readback. The low-temperature environment is part of what resonant scattering needs at the absorption edge, so this is a sample-side actuator CORA writes, not just a readback; the range and channel assignment are carried pending (TEMP-1).

The RASOR science detector is point detection, not an area detector. The scattered-beam point detector, the incident-flux monitor, the fluorescence channel, and the drain-current / total-electron-yield channel are read through Femto / SR570 current amplifiers and bind the catalog `FluxMonitor`; no area detector exists, so the science detector binds `FluxMonitor` rather than inventing a new kind (DET-1). See the [Detector](detector.md) page for that binding.

## The i10-1 / I10J magnet endstation (BL10J)

The i10-1 endstation holds the sample in an applied magnetic field at low temperature for X-ray magnetic dichroism (XMCD / XMLD). Its defining environment is the field: a set-and-read electromagnet and a superconducting field-sweep magnet, with the cryostat folded into the sample stages.

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `Electromagnet` | [`Magnet`](../../../catalog/families.md) | `BL10J-EA-MAGC-01:` | set-and-read field; graduated Family, a consumer of the 4-ID + i10-1 + ID32 rule-of-three (MAG-1) |
| `HighFieldMagnet` | [`Magnet`](../../../catalog/families.md) | `BL10J-EA-SMC-01:` | superconducting field-sweep magnet (Flyable); same `Magnet` family, the sweep is a per-Asset affordance (MAG-1) |
| `HighFieldMagnetStage` | [`LinearStage`](../../../catalog/families.md) | `BL10J-EA-MAG-01:` | the high-field magnet sample stage; the cryostat low-T folds into the stage (MAG-1) |
| `ElectromagnetStage` | [`LinearStage`](../../../catalog/families.md) | `BL10J-MO-CRYO-01:` | the electromagnet cryostat sample stage (MAG-1) |
| `MagnetTemperatureController` | [`TemperatureController`](../../../catalog/families.md) | `BL10J-EA-TCTRL-41:` | Lakeshore 336; presents `Regulator` (TEMP-1) |
| `MagnetSlit` | [`Slit`](../../../catalog/families.md) | `BL10J-AL-SLITS-` | the i10-1 sample-defining slit |
| `MagnetFocusingMirror` | [`Mirror`](../../../catalog/families.md) | `BL10J-OP-FOCA-01:` | the i10-1 branch focusing mirror |

Both magnet devices bind the graduated catalog `Magnet` family (MAG-1). They are one family, not two kinds: the electromagnet sets and reads a field, and the superconducting magnet adds a `Flyable` field sweep, but the sweep is a per-Asset affordance, not a split. No field values or sweep specifics are invented here (MAG-1). i10-1 was the family's second sighting after 4-ID, and with the later ESRF ID32 magnet it reached a rule-of-three and graduated into the catalog; it presents the `Regulator` Role, the field a settable process variable.

The two magnet sample stages reuse `LinearStage`; the cryostat low-temperature environment folds into the stage rather than earning its own kind (MAG-1). The Lakeshore 336 reuses the graduated `TemperatureController` presenting the `Regulator` Role, with range and channel assignment carried pending (TEMP-1). The i10-1 sample slit reuses `Slit` and the branch focusing mirror reuses `Mirror`, both catalog Families. The i10-1 science detection is again point detection (total-electron-yield, fluorescence, diode, and monitor channels), with no area detector, so it binds `FluxMonitor` (DET-1); see the [Detector](detector.md) page.

## Loose families at a second sighting

Two families on this page were first seen at 4-ID and have since graduated: `PolarizationAnalyzer` (the RASOR analysis arm, POL-2) and `Magnet` (the i10-1 electromagnet and superconducting magnet, MAG-1). Each was first seen at 4-ID and bound to a real device so the modelling is honest about what the endstation does.

`PolarizationAnalyzer` has since graduated to a catalog Family across 4-ID / i10 / ID32 / P09, presenting Positioner, so the arm binds the catalog Family (POL-2). `Magnet` has since graduated too: i10-1's second sighting, together with the later ESRF ID32 magnet, completed its rule-of-three, so the i10-1 magnets now bind the graduated catalog `Magnet` Family (MAG-1 now covers only the per-Asset field detail). Everything else on this page reuses a catalog Family unchanged.

## Why no new family here

Every device on both sample sides folds into vocabulary the fleet already carries or into a loose family already coined elsewhere, so this page changes the catalog by exactly nothing. The diffractometer is a `Goniometer` (DIFF-1); the reciprocal-space coordination is a `PseudoAxis` (DIFF-2); the cryostat stage and the magnet stages are `LinearStage` (STAGE-1, MAG-1); the pinhole is an `Aperture` (STAGE-1); the Lakeshore 340 and 336 are the graduated `TemperatureController` presenting `Regulator` (TEMP-1); the i10-1 slit and focusing mirror are `Slit` and `Mirror`.

The two things that could have tempted a new kind reuse existing families rather than coining one: the polarization-analysis arm binds the graduated catalog `PolarizationAnalyzer` (POL-2, earned across 4-ID / i10 / ID32 / P09), and the two magnet devices bind the graduated catalog `Magnet` (MAG-1), whose rule-of-three i10-1 helped complete alongside 4-ID and ESRF ID32. The one absence is the area detector: there is none at either endstation, so the point / current-integrating detection binds the catalog `FluxMonitor` rather than inventing an imaging Family (DET-1). The genuinely new modelling move at i10, polarization as a driven axis, sits on the source side as a reused `PseudoAxis`, not on the sample side (see [Model](../model.md)).

See [Open questions](../questions.md) for the sample-environment facts still to confirm and [Inventory](../inventory.md) for the Asset tree.
