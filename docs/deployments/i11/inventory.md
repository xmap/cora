# Inventory

*The CORA Asset model for I11: the planned device tree, the dodal-derived control handles, and what still needs confirming.*

I11 is a design-phase modelling exercise, so this is the planned Asset shape, not a registered inventory. It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages. The shape is generated-honest: it is authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i11/beamline.yaml) descriptor that the Source page renders from.

As at the other Diamond beamlines, the **control handles are known** (`BL11I` root, from dodal). Every device binds an existing catalog Family or a reused loose one. The `TemperatureController` graduation that i11 triggered has now landed via a gate-reviewed change: it is a catalog Family presenting the `Regulator` Role.

## The Asset tree

Root Asset `I11` (`tier = Unit`, `facility_code = diamond`). Bold families are loose design-intent names.

| Asset | Family | Control handle (dodal) | Notes |
| --- | --- | --- | --- |
| `I11` | (root) | | bound to the Diamond Site |
| `StorageRing` | **StorageRing** | | observe-only ring state; loose, reused from I22 |
| `DCM` | Monochromator | `BL11I-MO-DCM-01:` | double-crystal mono, Si(111) |
| `Slit1`..`Slit5` | Slit | `BL11I-AL-SLITS-0N:` | beam-defining slits |
| `Diffractometer` | RotaryStage | `BL11I-MO-DIFF-01:` | theta / two_theta / delta / spos; per-axis under a DiffractometerStage Assembly, NOT a Goniometer |
| `DiffractometerBase` | LinearStage | `BL11I-MO-DIFF-01:BASE:` | diffractometer base translation |
| `Spinner` | RotaryStage | `BL11I-EA-ENV-01:` | capillary spinner for powder averaging |
| `CyberstarBlower1` | TemperatureController | `BL11I-EA-BLOW-01:` | Cyberstar/Eurotherm continuous-setpoint blower |
| `CyberstarBlower2` | TemperatureController | `BL11I-EA-BLOW-02:LOOP1:` | autotuneable Cyberstar/Eurotherm blower |
| `Cryostream1` | TemperatureController | `BL11I-CG-CSTRM-01:` | Oxford Cryostream 700 plus |
| `Cryostream2` | TemperatureController | `BL11I-CG-CSTRM-02:` | Oxford Cryostream 700 standard |
| `Robot` | (Positioner, deferred) | `BL11I-EA-ROBOT-01:` | NX100 arm + carousel; one Positioner Asset + Subject + Clearance (I03 shape), not a new Family |
| `Mythen3` | Camera | `BL11I-EA-DET-07:` | 1D position-sensitive strip detector (Detector Role); skip-flagged in dodal |

Reused catalog Families (no new Family needed): `Monochromator`, `Slit`, `RotaryStage`, `LinearStage`, `Camera`, and `TemperatureController` (now a catalog Family, presenting the `Regulator` Role). Loose family reused from a sibling: `StorageRing` (from I22). The robot presents the existing Positioner Role (I03/19-BM pattern), shape deferred.

**The earn (now landed):** the four `TemperatureController` actuators made that family rule-of-three (I22 + I03 + I11), which earned graduating the `TemperatureController` catalog Family **and** a new settable-continuous-setpoint actuator Role (`Regulator`, requiring the `Settable` affordance). Because the Role is a code change (`SEED_ROLES`, drift-guarded) + core vocabulary, it was routed through the gate-review panel rather than the i11 scaffold; that gate-reviewed change has now landed (see the [Catalog](../../catalog/families.md)).

## Pending confirmations

Every value below is reverse-engineered from dodal or inferred, awaiting the beamline team. Each is tracked by an [open question](questions.md).

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Hutch PSS permit signals | both enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Which hutch each device sits in | all devices | `unknown-pending-confirmation` | (ENC-1) |
| Source type and energy range | `StorageRing` / source | `unknown-pending-confirmation` | (SRC-1) |
| DCM crystal d-spacing and thermal model | `DCM` | `unknown-pending-confirmation` | (OPT-1) |
| Storage-ring state modelling boundary | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| Mythen3 strip-detector Role choice and threshold / deadtime | `Mythen3` | `unknown-pending-confirmation` | (MYTHEN-1) |
| Diffractometer axis PVs, ranges, and arm geometry | `Diffractometer` | `unknown-pending-confirmation` | (DIFF-1) |
| Spinner speed range | `Spinner` | `unknown-pending-confirmation` | (SPIN-1) |
| Robot Asset, Clearance gate, and Subject custody lifecycle | `Robot` | `unknown-pending-confirmation` | (ROBOT-1) |
| Powder-diffraction Capability and Methods in scope | techniques | `unknown-pending-confirmation` | (TECH-1) |
| Hardware identity (serial numbers, asset tags) | all devices | `unknown-pending-confirmation` | (ID-1) |

Assertion-style questions that do not leave a value blank (the scope question SCOPE-1 and the diffractometer-not-goniometer decision GONIO-1) are on [Open questions](questions.md) without a placeholder here.
