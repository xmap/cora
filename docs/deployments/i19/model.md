# Model

*The developer's index into where i19 content lives, why the four-circle is not the novelty, what the dual-hutch access-control seam is, and the record of what is deliberately deferred. First cut.*

i19 is a descriptor-and-docs scaffold today, reverse-engineered from the beamline's dodal device layer: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/i19/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i19/beamline.yaml) | the device walk with bound PVs; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/diamond/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/diamond/site.yaml) | the Diamond facility surface; `I19` added to its beamline list, with a single-crystal diffraction Practice |
| Extraction provenance | [DiamondLightSource/dodal](https://github.com/DiamondLightSource/dodal) | the `src/dodal/beamlines/i19*.py` factories and `src/dodal/devices/` classes the descriptor was curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; every device reuses an existing catalog or loose Family (below) |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; the diffraction Method is pending, shared with 4-ID / 8-ID / CSX (TECH-1) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers i19 Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md); the dual-hutch access-control seam is the design-relevant part |

## What makes i19 new (and what does not)

i19 is CORA's first chemical (small-molecule) single-crystal crystallography beamline. The fleet's other diffraction-imaging crystallography is all macromolecular MX (I03, I24, FMX, MX3); i19 solves small-molecule structures on a Newport kappa four-circle goniometer with an Eiger detector, plus a serial / microfocus fixed-target arm.

The honest framing: the instrument is **not** the novelty. The kappa four-circle is plain catalog `Goniometer` reuse:

- The catalog `Goniometer` note states that **chi-versus-kappa and axis-count are a per-Asset setting, not a Family split**. So the phi / omega / kappa sample circles bind the catalog `Goniometer`, exactly as the i03 Smargon and the MX3 mini-kappa do.
- The larger four-circle (the goniometer plus the 2theta detector arm plus a reciprocal-space axis) composes the catalog `Assembly(Diffractometer)`, the 8-ID / 4-ID / i06-1 pattern, named-not-built in descriptor mode (`DIFF-1`, `DIFF-2`).
- The single-crystal diffraction technique reuses the pending `diffraction` Method that 4-ID, 8-ID, and CSX already share; chemical-versus-magnetic single crystal is a Practice-level science difference, not a new Method (`TECH-1`).

What **is** genuinely new is the governance seam, below. i19 coins no new Family and changes nothing in the catalog.

## The dual-hutch access-control seam

i19 has two experiment hutches in series (EH1 and EH2) that share one optics line, and only the active hutch may drive the shared optics. dodal expresses this through a central arbiter (the i19-blueapi optics service): a hutch reads the shared-optics state directly over EPICS, but its writes (change energy, operate the experiment shutter, move the attenuator, set a mirror piezo) are posted to the arbiter, which compares the requesting hutch against the active-hutch readback (`BL19I-OP-STAT-01:EHStatus`) and runs or rejects the operation.

CORA models this without a new device family:

- **The shared-optics devices are single Assets** in the `i19-optics` enclosure (the `Monochromator`, `Undulator`, the two `Mirror`s, the `Filter` attenuator, the `Shutter`). A non-active hutch reading them read-only is the same Asset surfaced through a permit, not a second Asset.
- **The active-hutch permit is an Enclosure-permit + Trust-gate.** EH1 and EH2 are two `Enclosure`s; which one may drive the shared optics now is a permit axis on the Enclosure, governed by Trust authorization. The `BL19I-OP-STAT-01:EHStatus` readback is the read-model of that permit (`ACCESS-1`).
- **The i19-blueapi arbiter is an actuate-floor seam partner.** It is the same shape as the "EPICS is the floor" seam, here a blueapi-arbiter floor: today it performs the active-hutch arbitration; CORA's edge would conduct the run over its `ControlPort`, either driving through the arbiter or replacing its plan-orchestration per routine, a seam decision not pre-empted here.

This is the design-interesting content of i19: an Enclosure-permit-gated actuate seam, the first dual-hutch shared-optics arbitration in the fleet. The concrete Enclosure-permit, Trust, and seam instances are named, not built, in this scaffold.

## No new families

Beyond the four-circle (Goniometer) and the MAPT aperture (below), the rest reuse the catalog directly: the DCM binds `Monochromator`; the focusing mirrors bind `Mirror` (the coating stripe is a hutch-keyed setting); the attenuator binds `Filter` (the i03 precedent); the undulator binds `InsertionDevice`; the Eiger and the OAV viewing cameras bind `Camera`; the Zebra and PandA hardware triggers bind `TimingController`; the serial / microfocus arm binds a second `Goniometer`; the beamstops bind `BeamStop`; the shutter binds `Shutter`; the incident energy is a `PseudoAxis`. The machine state reuses the loose `StorageRing`.

- **The MAPT pinhole and collimator bind the catalog `Aperture` (`APERTURE-1`).** This follows the i03 ApertureScatterguard-at-MAPT precedent: the consumer-facing beam-defining Asset binds `Aperture`, composing the pinhole and collimator XY stages, with the configuration aperture sizes as a Capability settings schema. The discriminator tension (the catalog `Aperture` describes a fixed code pattern, while the MAPT is a driven, size-selectable opening) is carried as `APERTURE-1`; the i03 sibling, the same controls stack and the same MAPT, already binds `Aperture`, so i19 follows it.

- **The sample backlight reuses the loose `Backlight` Family, its fourth sighting.** i03, i24, and fmx already bind it; i19 is the fourth consumer, and the Family stays held under review (the illumination-affordance fold-versus-promote question, `DET-1`). i19 adds a sighting, not a new Family.

## Deliberately not here yet

- **The Assembly(Diffractometer) and the reciprocal-space rule (`DIFF-1`, `DIFF-2`).** Named, not built, exactly as 4-ID, 8-ID, and i06-1 deferred theirs. The 2theta detector arm is a `RotaryStage` slot of the Assembly; det_z folds as a per-Asset axis on the arm (the i06-1 precedent).
- **The serial / microfocus raster (`SERIAL-1`).** The fixed-target arm binds a second `Goniometer`; the raster sub-mode (which would touch a grid-scan-style Method that the catalog does not yet carry) is carried as a note, not modelled.
- **The Enclosure-permit + Trust-gate + actuate seam instances (`ACCESS-1`).** The dual-hutch access-control is described above and is the governance novelty, but the concrete Zone / Conduit / Policy and the arbiter-seam drive-through-versus-replace decision are named, not built, in this scaffold.
- **The diffraction Method.** Whether single-crystal diffraction enters CORA's catalog as a Capability / Method is an owner decision; the Practice renders unlinked, pending, reusing the slug 4-ID / 8-ID / CSX share (`TECH-1`).
- **The centring image-recognition behaviour and the simulated devices.** The OAV pin-tip recognition is a Method behaviour on the Camera, not a device; no `test_i19_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
