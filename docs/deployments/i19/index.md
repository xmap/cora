# I19

*The small-molecule single-crystal diffraction beamline at Diamond Light Source, the fleet's first chemical crystallography beamline: monochromatic and variable-wavelength diffraction on a Newport kappa four-circle goniometer and an Eiger detector, plus a serial / microfocus fixed-target arm. The genuine novelty is not the instrument but the governance: two experiment hutches in series share one optics line, and only the active hutch may drive it. This page walks how CORA would model and govern I19; it is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `I19` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [Diamond Light Source](../diamond/index.md) (bound via `facility_code = "diamond"`, `FacilityKind = Site`) |
| Sector | `Sector 19` (PV zones `BL19I` / `SR19I`; two experiment hutches, EH1 and EH2, in series; not a registered Asset) |
| Status | First cut, reverse-engineered, design-phase (the shared optics and both hutches; PSS permit signals and vendor Models deferred) |
| Source | Undulator (`SR19I-MO-SERVC-01`), coordinated with the DCM on an energy move (`SRC-1`) |
| Control stack | Diamond EPICS / ophyd-async (the same floor as I22, I03, I15-1, I11, I24, I06, I10, I20-1), with the i19-blueapi optics service arbitrating the shared-optics writes; handles read from dodal, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) controls library (the `i19`, `i19_shared`, `i19_1`, and `i19_2` beamline factories and the `src/dodal/devices/` classes). EPICS PVs are real and read from dodal; vendor part numbers, serials, energy ranges, aperture sizes, and physical positions are not in dodal and are open questions. Every value is carried as `confirm` until I19 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes I19 different

I19 is CORA's first **chemical** crystallography beamline: it solves small-molecule single-crystal structures, where the rest of the fleet's diffraction-imaging crystallography is all **macromolecular** MX (I03, I24, FMX, MX3). It is worth being honest about where the novelty does, and does not, sit.

- **The instrument is not the novelty.** The Newport kappa four-circle is plain catalog `Goniometer` reuse. The catalog `Goniometer` note already states that chi-versus-kappa and axis-count are a per-Asset setting, not a Family split, so the phi / omega / kappa sample circles bind the catalog `Goniometer` exactly as the i03 Smargon does; kappa is a setting, not a new shape (`DIFF-1`). The larger four-circle (the goniometer plus the 2theta arm plus a reciprocal-space axis) composes the catalog `Assembly(Diffractometer)`, named-not-built, the 8-ID / 4-ID pattern (`DIFF-1`, `DIFF-2`).
- **The novelty is the dual-hutch shared-optics access-control seam.** I19 has two experiment hutches in series, EH1 and EH2, that share one optics line, and only the active hutch may drive that shared optics. dodal expresses this through a central arbiter, the i19-blueapi optics service: a hutch reads the shared-optics state directly over EPICS, but its writes (change energy, operate the experiment shutter, move the attenuator, set a mirror piezo) are posted to the arbiter, which compares the requesting hutch against the active-hutch readback (`BL19I-OP-STAT-01:EHStatus`) and runs or rejects the operation. CORA models this as an Enclosure-permit plus a Trust-gate over the shared-optics Assets, with the arbiter an actuate-floor seam partner: the same "EPICS is the floor" pattern, here a blueapi-arbiter floor (`ACCESS-1`). This is the first dual-hutch shared-optics arbitration in the fleet, and it is governance, **not a device family**.

The net: I19 coins no new Family, nothing graduates, and the catalog is unchanged. Its contribution is the first chemical-crystallography deployment and the first Enclosure-permit-gated actuate seam.

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Shared optics (`i19-optics`, `BL19I` / `SR19I`) | Yes | The undulator, the double-crystal monochromator, the two focusing mirrors with their hutch-keyed coating stripe (Si 5-10 / Rh 10-20 / Pt 20-30 keV), the absorber-wedge attenuator, the incident-energy pseudo-axis, and the PSS-interlocked optics shutter, all single Assets gated by the active hutch (`SRC-1`, `MONO-1`, `OPT-1`, `ATTN-1`, `PSS-1`, `ACCESS-1`) |
| EH1 endstation (`i19-1`) | Yes | The on-axis and diagonal OAV viewing cameras, the EH1 Zebra trigger box, and the EH1 beamstop (`DET-1`) |
| EH2 endstation (`i19-2`) | Yes | The Newport kappa four-circle bound to `Goniometer`, the reciprocal-space pseudo-axis, the Eiger area detector, the serial / microfocus arm, the MAPT pinhole and collimator bound to `Aperture`, the EH2 beamstop, the sample backlight, and the Zebra and PandA trigger hardware (`DIFF-1`, `DIFF-2`, `SERIAL-1`, `APERTURE-1`, `DET-1`) |
| The dual-hutch active-hutch permit and arbiter | Named, not built | The Enclosure-permit plus Trust-gate plus actuate-floor seam is described, but the concrete Zone / Conduit / Policy and the arbiter drive-through-versus-replace decision are deferred (`ACCESS-1`) |
| The Assembly(Diffractometer) and the serial raster sub-mode | Named, not built | The 2theta arm is a `RotaryStage` slot of the Assembly; the serial fixed-target raster is carried as a note, not a Method (`DIFF-1`, `SERIAL-1`) |
| PSS search-and-secure permit signals | No | Beyond the dodal InterlockedHutchShutter, carried pending, not invented (`PSS-1`) |
| Vacuum extent and the simulated devices | No | Carried pending, not invented (`SUP-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **The kappa four-circle binds the catalog `Goniometer`; kappa is a setting (`DIFF-1`).** This is reuse, not a new Family: the catalog `Goniometer` note states that chi-versus-kappa and axis-count are a per-Asset setting or bound-Model difference, not a Family split. The phi / omega / kappa sample circles bind `Goniometer`; the larger four-circle (the goniometer plus the 2theta detector arm plus det_z plus a reciprocal-space axis) is the named-not-built `Assembly(Diffractometer)` (`DIFF-2`).
- **Single-crystal diffraction reuses the pending `diffraction` Method (`TECH-1`).** 4-ID, 8-ID, and CSX are the prior consumers; chemical-versus-magnetic single crystal is a Practice-level science difference, not a new Method.
- **The MAPT pinhole and collimator bind the catalog `Aperture` (`APERTURE-1`).** This follows the i03 MAPT precedent: the beam-defining Asset composes the pinhole and collimator stages, with the selectable aperture sizes as a Capability settings schema.
- **The dual-hutch shared-optics access-control is the genuine novelty: an Enclosure-permit plus Trust-gate plus actuate-floor seam (the i19-blueapi arbiter), not a device family (`ACCESS-1`).** EH1 and EH2 are two `Enclosure`s; which one may drive the shared optics now is a permit axis on the Enclosure, governed by Trust, with `BL19I-OP-STAT-01:EHStatus` the read-model of that permit. A non-active hutch reading the shared optics read-only is the same single Asset surfaced through the permit (`MONO-1`, `OPT-1`, `ATTN-1`, `PSS-1`).
- **The sample backlight reuses the loose `Backlight` Family, its fourth sighting, held (`DET-1`).** i03, i24, and fmx already bind it; I19 adds a sighting, not a new Family. Zero new families coined, nothing graduates, the catalog is unchanged.

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the machine-level storage-ring state (observe-only, `MACHINE-1`), the undulator coordinated with the DCM on an energy move (`SRC-1`), the double-crystal monochromator (`MONO-1`), the horizontal and vertical focusing mirrors whose coating stripe (Si 5-10 / Rh 10-20 / Pt 20-30 keV) is a hutch-keyed setting (`OPT-1`), the absorber-wedge attenuator (`ATTN-1`), the incident-energy pseudo-axis (`MONO-1`), and the PSS-interlocked optics shutter (`PSS-1`). Every write to these shared-optics Assets is gated by the active-hutch permit (`ACCESS-1`).
- [Sample](equipment/sample.md): the EH2 Newport kappa four-circle and its sample circles (`DIFF-1`), the reciprocal-space pseudo-axis (`DIFF-2`), the serial / microfocus fixed-target arm bound to a second `Goniometer` (`SERIAL-1`), the MAPT pinhole and collimator aperture (`APERTURE-1`), the EH1 on-axis and diagonal OAV viewing cameras, and the sample backlight held under review (`DET-1`).
- [Detector](equipment/detector.md): the Eiger area detector in EH2, the two beamstops, and the Zebra and PandA hardware triggering, where the PandA-versus-Zebra choice is a bound-Model difference (`DET-1`).

Cutting across them, and central to the dual-hutch shape:

- [Controls](equipment/controls.md): the Diamond EPICS / ophyd-async control stack and the i19-blueapi arbiter that decides which hutch may drive the shared optics; CORA's edge would conduct the run over its `ControlPort`, either driving through the arbiter or replacing its plan-orchestration per routine, a seam decision not pre-empted here. Handles read from dodal and carried confirm (`CTRL-1`).

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i19/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of I19 is designed to do, as intent. Single-crystal diffraction shares the pending `diffraction` Method that 4-ID, 8-ID, and CSX already carry; chemical-versus-magnetic single crystal is a Practice-level difference, so I19 coins no new Method. The Site Practice `I19_diffraction_practice` renders pending at the [Diamond Site](../diamond/index.md#the-techniques-adapted-here) (`TECH-1`).

## Governance

[Governance](governance.md): who would act at I19 and the trust shape (Zone plus Conduit plus Policy) that gates their commands. People and autonomous agents are facility principals at the [Diamond Site](../diamond/index.md#who-acts-here), carried pending site-level (`GOV-1`), following the 2-BM governance shape. The I19-specific governance element is the dual-hutch active-hutch permit: which hutch may drive the shared optics is an Enclosure-permit plus Trust-gate, with the i19-blueapi arbiter the actuate-floor seam partner (`ACCESS-1`, `ENC-1`). The PSS search-and-secure permit signals are carried pending, not invented beyond the dodal InterlockedHutchShutter (`PSS-1`); the hazard envelope is a hard X-ray beamline with two experiment hutches in series sharing one optics line (see [the safety envelope](../diamond/index.md#the-safety-envelope)).

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's I19 content lives, why this first chemical-crystallography deployment coins no new vocabulary (the four-circle is `Goniometer` reuse, kappa a setting), what the dual-hutch access-control seam is, and the record of what is deliberately deferred.

## Not yet documented

I19 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The concrete Enclosure-permit, Trust, and arbiter-seam instances are named, not built, in this scaffold (`ACCESS-1`); the PSS search-and-secure permit signals are carried pending, not invented beyond the dodal InterlockedHutchShutter (`PSS-1`); and the vacuum extent and the simulated devices are carried pending (`SUP-1`).
