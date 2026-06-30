# Sample

*The i06 sample side across both endstations. Design-phase; PVs read from dodal, carried confirm.*

i06 carries two sample sides, one per endstation. The i06-1 diffraction-dichroism hutch (BL06J) holds the sample circles that orient a crystal in the polarized soft X-ray beam, an absorption stage, and a pair of Lakeshore temperature controllers for the in-situ thermal environment. The i06-2 PEEM hutch (BL06K) holds the UHV sample manipulators that position the photoemitting surface in front of the electron-imaging column. Both are modelled flat in the [descriptor](../inventory.md), grouped only when a feature must act on the whole.

Neither side coins a Family. The diffraction circles reuse `Goniometer`, the absorption stage reuses `LinearStage`, the Lakeshores reuse the graduated `TemperatureController`, and the PEEM manipulators reuse the graduated `Manipulator`. The genuinely new thing at i06, the polarization axis, lives on the source side, not here (see the generated [Source](../beamline.md) walk and the [Beam axes](../inventory.md#the-asset-tree) entries).

## The i06-1 diffraction-dichroism circles (BL06J)

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `Diffractometer` | [`Goniometer`](../../../catalog/families.md) | `BL06J-EA-DDIFF-01:` | the diffraction-dichroism sample circles (x / y / z, theta incidence, chi / phi) plus the `DET:2THETA` / `DET:Y` detector arm; circle roles and whether they compose an Assembly are pending (DIFF-1) |
| `ReciprocalSpace` | [`PseudoAxis`](../../../catalog/families.md) | (over the circles) | the reciprocal-space axis over the diffractometer circles; the inverse-kinematics rule is deferred (DIFF-2) |

The diffractometer reuses the catalog `Goniometer`, the Family the rotation-MX and soft X-ray diffraction siblings already earned. Its circles set the scattering geometry for resonant soft X-ray diffraction and dichroism, with the `DET:2THETA` / `DET:Y` arm carrying the detector position; the circle roles are carried pending (DIFF-1). The reciprocal-space coordination over those circles is a `PseudoAxis`, a sibling of the energy and polarization axes, with the inverse-kinematics rule deferred exactly as 4-ID, 8-ID, and CSX deferred theirs (DIFF-2). Whether the circles plus the detector arm compose an `Assembly(Diffractometer)` is named, not built; the first cut is the flat `Goniometer` Asset plus the reciprocal-space axis (DIFF-1).

The i06-1 scattering detector and any incident-flux or drain-current (electron-yield) monitor are absent from dodal, so only the detector-arm motors are modelled here; the detectors are bound later from outside dodal and no detector Family is invented in the meantime (DET-1). See the [Detector](detector.md) page for that deferral.

## The i06-1 absorption stage (BL06J)

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `AbsorptionStage` | [`LinearStage`](../../../catalog/families.md) | `BL06J-EA-XABS-01:` | the XAS / absorption sample stage (x / y / theta); bound to `LinearStage` as a design-phase placeholder (STAGE-1) |

The absorption stage reuses `LinearStage` as a design-phase placeholder. It carries a translation pair plus a theta, which is the open question: whether that theta (alongside the diffractometer chi / phi) warrants a `Goniometer` plus an Assembly rather than the flat `LinearStage` is carried as STAGE-1, not decided here. The conservative first cut binds the simpler Family and earns the richer one only if the theta proves to be a true sample-orienting circle.

## The i06-1 temperature environment (BL06J)

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `CoolingController` | [`TemperatureController`](../../../catalog/families.md) | `BL06J-EA-TCTRL-02:` | Lakeshore 336 sample cooling; presents `Regulator` (TEMP-1) |
| `HeatingController` | [`TemperatureController`](../../../catalog/families.md) | `BL06J-EA-TCTRL-03:` | Lakeshore 336 sample heating; presents `Regulator` (TEMP-1) |

The two Lakeshore 336 controllers reuse the graduated `TemperatureController` Family, which presents the `Regulator` Role: a settable setpoint with a readback. Cooling versus heating is a per-Asset setting on the same Family, not two kinds; both bind the one catalog Family. The cooling and heating ranges and the channel assignment are carried pending (TEMP-1). The in-situ temperature environment is part of what magnetic dichroism needs at the absorption edge, so these are sample-side actuators CORA writes, not just readbacks (subject to TEMP-1).

## The i06-2 PEEM sample manipulators (BL06K, BL06I)

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `PeemManipulator` | [`Manipulator`](../../../catalog/families.md) | `BL06K-MO-PEEM-01:` | the PEEM UHV sample manipulator (x / y / phi) plus the energy-slit translation; axis set pending (MANIP-1) |
| `PeemSampleStage` | [`Manipulator`](../../../catalog/families.md) | `BL06I-MO-PEEM-01:` | the i06-branch PEEM sample stage (x / y / phi); axis set pending (MANIP-1) |

The two PEEM sample manipulators reuse the catalog `Manipulator` Family, the abstraction graduated across SIX and ESM (the UHV-sample-manipulator precedent). The `peem` unit carries x / y / phi plus an energy-slit translation; the energy slit is a per-Asset axis on the Family, not a new kind. The i06-branch sample stage on the optics zone (BL06I) carries the same x / y / phi shape. The axis sets are carried pending (MANIP-1). These manipulators position the photoemitting surface for the imaging measurement, the way the ESM and SIX manipulators orient the sample for their analyzers.

The PEEM technique's defining instrument, the electron-optical column that forms a magnified electron image of the surface and the detector that records it, is absent from dodal: dodal binds the manipulator and its energy slit, not the column or the image detector. That column is the `ElectronMicroscope` anatomy, an electron-imaging column distinct from the photon `Camera` and from the energy-analyzing catalog `ElectronAnalyzer` of ARPES. It is deferred, not coined here; binding a Family with no PV would create an orphan (PEEM-1). See the [Detector](detector.md) page for that deferral.

## Why no new family here

Every device on both sample sides folds into vocabulary the fleet already carries, so this page changes the catalog by exactly nothing. The diffraction circles are a `Goniometer`; the absorption stage is a `LinearStage` placeholder (STAGE-1); the Lakeshores are the graduated `TemperatureController` presenting `Regulator` (TEMP-1); the PEEM manipulators are the graduated `Manipulator` (MANIP-1). The reciprocal-space coordination is a `PseudoAxis`, the same primitive the incident-energy and polarization axes use.

The two things that could have tempted a new kind are both absences, not inventions: the i06-1 scattering detector and flux monitor (DET-1) and the PEEM electron-imaging column and its image detector (PEEM-1) are not in dodal, so they are deferred and named rather than coined. The genuinely new modelling move at i06, polarization as a driven axis, sits on the source side as a reused `PseudoAxis`, not on the sample side (see [Model](../model.md#what-makes-i06-new)).

See [Open questions](../questions.md) for the sample-environment facts still to confirm and [Inventory](../inventory.md) for the Asset tree.
