# Sample

*The i19 sample side, in EH2. Design-phase scaffold; values are reverse-engineered from dodal or inferred, and every uncertain one carries its question id.*

The sample side is where i19 does chemical crystallography: the Newport kappa four-circle that orients a single crystal, the serial / microfocus fixed-target arm beside it, the MAPT microfocus aperture that defines the beam onto the sample, and the on-axis viewing cameras that centre a pin. It sits in the EH2 experiment hutch (`i19-2`); which hutch holds the four-circle is itself a confirmation (ENC-1), and the descriptor places it in EH2. This is the page where the most natural temptation, to coin a four-circle Family, is the wrong move, and the [why-no-new-family note](#why-no-new-family-here) below says why.

## The four-circle (plain Goniometer reuse)

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `Diffractometer` | [`Goniometer`](../../../catalog/families.md) | `BL19I-MO-CIRC-02:` | the Newport kappa four-circle sample circles: phi / omega / kappa, with sample-centring on `BL19I-MO-SAMP-02` (DIFF-1) |
| `ReciprocalSpace` | [`PseudoAxis`](../../../catalog/families.md) | (derived) | reciprocal-space axis driven over the four-circle, named-not-built (DIFF-2) |

The kappa four-circle is **catalog `Goniometer` reuse, not a new Family**. The catalog `Goniometer` note states that chi-versus-kappa and axis count are a per-Asset setting, not a Family split, so the phi / omega / kappa sample circles bind `Goniometer` exactly as the i03 Smargon and the MX3 mini-kappa do; kappa is the setting (DIFF-1). The larger four-circle, the sample circles plus the 2theta detector arm plus det_z plus the reciprocal-space axis, composes the catalog `Assembly(Diffractometer)`, the 4-ID / 8-ID / i06-1 pattern, **named, not built** in descriptor mode (DIFF-1). The 2theta arm folds as a `RotaryStage` slot of that Assembly and det_z as a per-Asset axis on the arm (the i06-1 precedent); the reciprocal-space partition rule is carried pending (DIFF-2). The real dodal sample-centring and circle motors are the controls-layer realization, not separate spine Assets.

Single-crystal diffraction here **reuses the pending `diffraction` Method** that 4-ID, 8-ID, and CSX already share; chemical-versus-magnetic single crystal is a Practice-level science difference, not a new Method (TECH-1).

## The serial / microfocus arm

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `SerialStage` | [`Goniometer`](../../../catalog/families.md) | `BL19I-MO-SRL-01:` | the serial / microfocus fixed-target arm: x / y / z / phi (SERIAL-1) |

Beside the four-circle, the fixed-target arm binds a **second `Goniometer`**: x / y / z translation plus a phi rotation is the same role-noun, again with axis count as a per-Asset setting. The raster sub-mode, the grid-style scan a fixed-target serial collection drives across the mounted chip, would touch a grid-scan-style Method the catalog does not yet carry, so it is **carried as a note, not modelled** (SERIAL-1).

## The microfocus aperture

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `Aperture` | [`Aperture`](../../../catalog/families.md) | `BL19I-MO-PIN-01:` + `BL19I-MO-COL-01:` | the MAPT pinhole plus collimator microfocus aperture; sizes from config table `BL19I-OP-PCOL-01:CONFIG` (APERTURE-1) |

The MAPT pinhole and collimator are the consumer-facing beam-defining Asset onto the sample, and they bind the catalog `Aperture`, following the **i03 MAPT precedent** (APERTURE-1). It composes the pinhole and collimator XY stages, and the selectable aperture sizes are a **Capability settings schema** read from the configuration table. The discriminator tension, that the catalog `Aperture` describes a fixed code pattern while the MAPT is a driven, size-selectable opening, is carried as APERTURE-1; the i03 sibling runs the same controls stack and the same MAPT and already binds `Aperture`, so i19 follows it. No aperture sizes are invented here; they are read from `BL19I-OP-PCOL-01:CONFIG` pending confirmation (APERTURE-1).

## The viewing cameras

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `SampleViewerOnAxis` | [`Camera`](../../../catalog/families.md) | `BL19I-EA-OAV-01:` | the on-axis OAV viewing camera (in EH1, `i19-1`) (DET-1) |
| `SampleViewerDiagonal` | [`Camera`](../../../catalog/families.md) | `BL19I-EA-OAV-02:` | the diagonal OAV viewing camera (in EH1, `i19-1`) (DET-1) |
| `Backlight` | `Backlight` (loose) | `BL19I-EA-IOC-12:` | sample backlight in / out; fourth sighting, held under review (DET-1) |

The OAV viewing cameras bind `Camera`. The thing that makes them interesting, **pin-tip recognition for centring, is a Method behaviour, not a device**: the image-recognition step that finds the crystal pin and drives the goniometer to centre it lives on the Camera as behaviour, so it adds no Family and no Asset (DET-1). The sample backlight reuses the loose `Backlight` Family, its **fourth sighting** after i03, i24, and fmx; the Family stays held under review (the illumination-affordance fold-versus-promote question), so i19 adds a sighting, not a new Family (DET-1).

## Why no new family here

The four-circle is the page's whole modelling argument. A kappa four-circle goniometer is the kind of instrument that tempts a new `FourCircle` or `Diffractometer` Family, and i19 deliberately does not coin one:

- **The circles are a `Goniometer`.** The catalog `Goniometer` note already settles that chi-versus-kappa and axis count are a per-Asset setting, not a Family split. kappa is a setting. The phi / omega / kappa sample circles bind `Goniometer` (DIFF-1), the same as the i03 Smargon and the MX3 mini-kappa, and the serial arm binds a second `Goniometer` (SERIAL-1).
- **The whole four-circle is an Assembly, not a Family.** The sample circles plus the 2theta arm plus det_z plus the reciprocal-space axis compose `Assembly(Diffractometer)`, named-not-built, the 4-ID / 8-ID / i06-1 pattern (DIFF-1, DIFF-2). Composition, not a new role-noun.
- **The aperture and backlight reuse too.** The MAPT binds `Aperture` on the i03 precedent (APERTURE-1); the backlight is the loose `Backlight`'s fourth sighting (DET-1).

i19 is CORA's first chemical (small-molecule) crystallography beamline, and even so the sample side coins **no new Family and changes nothing in the catalog**. The genuine i19 novelty is elsewhere: the dual-hutch shared-optics access-control seam, a governance concern over the shared optics, not a device family (ACCESS-1). See the [Model](../model.md#the-dual-hutch-access-control-seam) page for that seam, the [Source](../beamline.md) walk for the shared optics and the EH1 / EH2 endstation devices in the descriptor, and the [Inventory](../inventory.md) for the full Asset tree.
