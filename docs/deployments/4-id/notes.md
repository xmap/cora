# Notes

## Techniques

*What the modelled part of 4-ID is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../aps/index.md#the-techniques-adapted-here) is how a facility adapts it. 4-ID's techniques are diffraction, magnetism, and polarization, none of which exist in CORA's imaging-heritage catalog yet, so the Methods below render unlinked and are carried pending until one enters the pilot scope (`TECH-1`). The function view survives the eventual hardware and catalog choices, which is why it can be written before the Methods are coined.

### Single-crystal diffraction

The Huber diffractometers at 4-ID-G orient a single crystal and scan reciprocal space, measuring scattered intensity as a function of momentum transfer.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| X-ray diffraction | `diffraction` | reciprocal-space scans on the Eulerian or high-pressure diffractometer; Method not yet in catalog |
| High-pressure diffraction | `diffraction` | the high-pressure diffractometer with a pressure cell; a Plan setting over the same Method |

Both need the [diffractometers](sample.md) and the [detectors](detector.md). Whether the reciprocal-space coordination (hklpy2) is modelled as a `PseudoAxis` inside an `Assembly(Diffractometer)` is the design recorded on [Model](#deliberately-not-here-yet); the world-fact half (the circle geometry) is `DIFF-1`.

### Magnetic and resonant scattering

4-ID's signature: resonant scattering across an absorption edge, in an applied magnetic field and at low temperature, to probe magnetic and electronic order.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Resonant magnetic scattering | `magnetic_scattering` | scattering in field (2 T or high-field magnet) at low temperature; Method not yet in catalog |
| Resonant elastic scattering | `resonant_scattering` | energy-resonant scattering across an edge; Method not yet in catalog |

These need the [sample environment](sample.md) (magnet plus temperature controller) and the monochromator's energy control.

### Polarization analysis

The phase retarders set the incident X-ray polarization, and the polarization analyzer resolves the scattered-beam polarization; together they enable dichroism and polarization-dependent scattering.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| X-ray magnetic circular dichroism | `xmcd` | circular polarization set by the phase retarders; Method not yet in catalog |
| Polarization-analyzed scattering | `magnetic_scattering` | the analyzer crystal resolves the scattered polarization; a Plan setting over the scattering Method |

These need the [phase retarders and polarization analyzer](sample.md).

### Not modelled yet

The Raman station's techniques are out of this cut (`TOPO-2`). The concrete acquisition recipes (scan sequences, energies, fields, exposures) are not written yet; they join as the deployment approaches the point where CORA drives 4-ID. Whether diffraction and the polarization / magnetism Methods enter CORA's catalog at all is an owner-scope decision recorded on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at 4-ID, and the trust shape that will gate it. First cut.*

Governance at 4-ID follows the same model as the 2-BM pilot: people and autonomous agents are facility principals at the [APS Site](../aps/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

4-ID is not yet driven by CORA, so this shape is not yet instantiated. The 4-ID operator pool and beamline-scientist assignments are not modelled ahead of confirmation; CORA does not invent a 4-ID operator roster (a placeholder `4-ID Beamline Scientist` is carried pending on the [APS Site](../aps/index.md#safety-and-governance)).

What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [APS Site](../aps/index.md#safety-and-governance), not on the beamline, and the beamline links up to them rather than restating them. 4-ID adds hazard classes beyond the imaging envelope, superconducting magnets with high stored energy and cryogens, a pump-probe laser, and pressurized high-pressure cells, that an experiment Clearance would carry; those land with the instruments that bring them as the sample environment firms (`MAG-1`, `SAMPLE-1`).

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives 4-ID, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's 4-ID content lives, the diffraction / magnetism / polarization deployment whose loose families graduated across the fleet, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at 4-ID |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### Loose-Family graduation

4-ID introduced eight device classes CORA had not earned into the catalog. Graduation needs two or more independent CORA deployments AND a settled abstraction. The 8-ID XPCS deployment adds the second independent beamline for `TemperatureController`, `Transfocator`, and `PositionMonitor`. `TemperatureController` has since graduated to a catalog Family: the parallel Diamond i22/i03/i11 rule-of-three settled the settable-actuator abstraction, and it presents the new `Regulator` Role. `Transfocator` has likewise graduated to a catalog Family: a CRL focusing optic earned across eight deployments, so 4-ID's CRL now reuses it like any catalog Family (its lens material and lenslet count stay a per-Asset spec, `OPT-2`). `PhaseRetarder` has likewise graduated to a catalog Family: a phase-retarder optic earned across 4-ID (three diamond phase-retarder stages), PETRA III P09 (shared phase-retarder circles), and PETRA III P22 (a third consumer via the shared P09 optics), and it presents the `Positioner` Role. `PolarizationAnalyzer` has likewise graduated to a catalog Family: a polarization-analysis positioner earned across 4-ID / i10 / ID32 / P09, so 4-ID's analyzer now reuses it like any catalog Family (its analyzer-crystal spec stays a per-Asset detail, `POL-2`). `PositionMonitor` has likewise graduated to a catalog Family: its own Sensor Family earned across the wide fleet that shares it (APS 4-ID/8-ID/9-ID, the NSLS-II beamlines, and the imaging and MX beamlines), the cross-facility review resolving the fold-vs-promote question in favour of promote (distinct from the graduated `FluxMonitor` by measuring beam position and centroid, not flux; the per-Asset position-versus-intensity split stays open, `BPM-1`). The `Diffractometer` is the one that landed: as the `Assembly(Diffractometer)` blueprint (4-ID + 8-ID), which composes the catalog `Goniometer` Family, with an 8-ID Fixture scenario. `Magnet` has since graduated to a catalog Family: 4-ID was its first consumer, and the Diamond i10-1 and ESRF ID32 magnets brought it to a rule-of-three, settling the settable-field abstraction, so it presents the `Regulator` Role like `TemperatureController` (its per-Asset field range and control handles stay a per-Asset spec, `MAG-1`). `Laser` has since graduated to a catalog Family: an optical sample laser earned across 4-ID, LCLS-MFX, and the PSI SwissFEL endstations (Alvra, Bernina, Cristallina), one Family spanning pump-probe and alignment/reference lasers as a per-Asset purpose (SAMPLE-1). All names were cleared by the naming-r3 review during the catalog-graduation pass.

| Loose Family | Presents (when graduated) | Status |
| --- | --- | --- |
| `TemperatureController` | Regulator | GRADUATED: catalog Family on the Diamond i22/i03/i11 rule-of-three; presents Regulator, requires Settable; 4-ID device details still to confirm (TEMP-1) |
| `Transfocator` | Positioner | GRADUATED: catalog Family, a CRL focusing optic earned across eight deployments; 4-ID's CRL reuses it, lens spec still to confirm (OPT-2) |
| `PositionMonitor` | Sensor | GRADUATED: catalog Family presenting Sensor, earned across the wide fleet that shares it; distinct from FluxMonitor by measuring beam position not flux; 4-ID position-vs-intensity split still to confirm (BPM-1) |
| `PhaseRetarder` | Positioner | GRADUATED: catalog Family across 4-ID / P09 / P22; presents Positioner; 4-ID phase-retarder specs still to confirm (POL-1) |
| `PolarizationAnalyzer` | Positioner | GRADUATED: catalog Family across 4-ID / i10 / ID32 / P09; presents Positioner, analyzer-crystal spec still to confirm (POL-2) |
| `Magnet` | Regulator | GRADUATED: catalog Family on the 4-ID + i10-1 + ID32 rule-of-three; presents Regulator, the field a settable process variable; 4-ID device field ranges and control PVs still to confirm (MAG-1) |
| `Laser` | (no Role) | GRADUATED: catalog Family, an optical sample laser earned across 4-ID / LCLS-MFX / Alvra / Bernina / Cristallina, one Family spanning pump-probe and alignment/reference lasers as a per-Asset purpose; the SAMPLE-1 model-versus-hazard question stays open |
| `Diffractometer` | Positioner (Assembly) | LANDED as `Assembly(Diffractometer)` in the catalog, composing `Goniometer` (4-ID + 8-ID); 8-ID Fixture scenario landed, the 4-ID Fixture is the follow-on |

### Deliberately not here yet

These are the parts of 4-ID this cut leaves out on purpose. Each is a CORA scope decision, not a fact the beamline team needs to supply, so it lives here rather than on [Open questions](#open-questions).

- **The 4-ID Diffractometer Fixture.** The `Assembly(Diffractometer)` is now in the catalog (composing the `Goniometer` Family) and materialized by the 8-ID Fixture scenario (see the [8-ID model page](../8-id/notes.md#the-diffractometer-assembly-landed)). 4-ID's two Huber diffractometers (the Eulerian cradle and the high-pressure diffractometer) are still modelled here as plain devices with their circle axis maps; decomposing them into a `Goniometer` Asset (the sample circles plus centring) plus any detector-arm `RotaryStage` circles and binding a 4-ID Fixture is the follow-on, gated on the circle-role confirmation (`DIFF-1`). The Assembly is the shared blueprint; the Fixture is per-beamline.

- **The Raman station.** `4-ID-Raman` is out of this cut because its device config did not extract (a symlink that did not resolve in the source clone). Its devices and whether it is a fifth enclosure are `TOPO-2`; it is a world-fact gap, tracked on [Open questions](#open-questions), not a scope decision.

- **The 6-ID-B fork and the psic diffractometer.** A second instrument repo, `BCDA-APS/6idb-bits`, is a fork of `polar-bits`: its devices are almost entirely the same `4id*` PVs, with a grafted 6-ID-B endstation (a `psic` six-circle diffractometer at `6idb1:`, a CRL at `6idbSoft:TRANS:`). It is not an independent beamline, so it was used only as a second source to enrich this 4-ID descriptor (the `emag` magnet axes, the Euler diffractometer chi/phi circles), not to build a 6-ID-B deployment. The genuine 6-ID-B endstation (the `psic` diffractometer) is a future deployment, not modelled here. This fork also means the fleet recurrence report counts `polar-bits` and `6idb-bits` as two beamlines when they are one physical beamline, so 4-ID's own recurrence signal for `Magnet` / `TemperatureController` / `Diffractometer` rests on a single beamline (each of these has since graduated on a rule-of-three earned across other beamlines: `Magnet` at i10-1 and ID32).

- **The diffraction / magnetism / polarization Methods.** Whether these techniques enter CORA's catalog (which has been all-imaging) is an owner decision. The Practices are registered pending and render unlinked; no Method is coined until the technique enters the pilot scope (`TECH-1`).

- **Peripheral electronics.** The preamplifiers, lock-in amplifier, LabJacks, and high-pressure-cell controllers are present in the beamline config but not modelled as Assets in this cut (`SAMPLE-2`). They join if they prove to be beamline equipment CORA should track.

- **Integration scenarios and vendor Models.** No `test_4id_*.py` registers 4-ID Assets, and no vendor Models are bound. Scenario code is where Assets become real; hard-registering a first-cut, confirm-pending beamline would commit speculative structure. Both land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the 4-ID team to confirm before the model can be trusted.*

4-ID was reverse-engineered from the beamline's own Bluesky instrument repo ([BCDA-APS/polar-bits](https://github.com/BCDA-APS/polar-bits)), so the control handles on the [device pages](index.md) are the beamline's real PVs, but read from a config snapshot rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are recorded on [Model](#deliberately-not-here-yet) instead, including which loose Families graduate and the diffractometer Assembly). It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed, with the reason in the commit. Priorities are `Blocks-build` (the answer changes the structure of the model), `Blocks-go-live` (a placeholder is fine for the description, but the real value is needed before CORA observes or drives the hardware), and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TOPO-1 | Blocks-build | Do the three experiment stations (`4-ID-B`, `4-ID-G`, `4-ID-H`) run off one beam in series, or are any canted / branched off separate beams? Which optics are shared versus per-station? | One root Unit Asset `4-ID` with one optics spine feeding the three stations; KB mirrors and filters are per-station. | One-vs-many beam walks and the shared-vs-per-station optics split in the [descriptor](index.md). |
| TOPO-2 | Blocks-go-live | The `4-ID-Raman` station: what instruments and devices does it carry? (Its `devices.yml` is a symlink that did not resolve in the source clone, so it did not extract.) | The Raman station exists but is out of this cut. | The Raman station devices and a fifth enclosure if warranted. |
| TOPO-3 | Nice-to-have | Two PVs gave ambiguous station hints: `4iddMZ0:` (the SGZ Vortex detector) and `4idkepco:` (a Kepco magnet supply). What station does each sit in? | The Vortex is placed at `4-ID-G` and the Kepco magnet at `4-ID-G`, both confirm. No `4-ID-D` / `4-ID-K` enclosures are declared. | The station assignment for those two devices. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the polar-bits config current and correct for each device? | The handles in the descriptor are taken from the config and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | What are the PSS search-and-secure permit signals for the four hutches (`4-ID-A/B/G/H`)? | Four hutches exist with permit signals to be named. | The Enclosure permit signals. |

### Sources and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The undulator pair on S04ID: device types, periods, and gaps. | One `InsertionDevice` Asset for the pair (`PolarUndulatorPair`); periods unconfirmed. | The insertion-device specs. |
| SRC-2 | Nice-to-have | Should the pair be one Asset or two (one per undulator)? | Modelled as one Asset. | One-vs-two source Assets. |
| MONO-1 | Blocks-go-live | The VDCM monochromator: energy range, crystal set behind `crystal_select`, and per-axis roles. | One `Monochromator` Asset (4idVDCM) with a crystal-select axis; range unconfirmed. | The monochromator energy model. |
| OPT-1 | Nice-to-have | The toroidal pre-focusing mirror and the HHL bendable mirror: coatings, stripes, and the bender / piezo axis roles. | Two `Mirror` Assets; the HHL axis map is taken from the config, coatings unconfirmed. | The mirror specs. |
| OPT-2 | Blocks-go-live | The transfocator (`4idPyCRL:CRL4ID:`): lens material, count, and which stations it focuses. | One `Transfocator` Asset (catalog Family); serves 4-ID-G and 4-ID-H. | The transfocator spec. |
| OPT-3 | Nice-to-have | The per-station KB mirror (`bkb`/`gkb`/`hkb`) internal axis maps. | Three `Mirror` Assets; only the 4-ID-B KB carries a partial axis map. | The KB axis maps. |

### Polarization

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| POL-1 | Blocks-go-live | The three phase retarders (`pr1`/`pr2`/`pr3`): diamond crystal type, thickness, and how they coordinate to set a polarization state. | Three `PhaseRetarder` Assets (catalog Family), each th/x/y, energy-tracking. | The phase-retarder specs and the polarization-state model. |
| POL-2 | Blocks-go-live | The polarization analyzer (`pol`, th/y): analyzer crystal and the scattered-beam polarization it resolves. | One `PolarizationAnalyzer` Asset (catalog Family) at 4-ID-B. | The analyzer spec. |

### Diffractometer

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-build | The Huber Eulerian and high-pressure diffractometers: the real circle set (4-circle Eulerian? 6-circle?) and which motor is which circle (omega, chi, phi, two-theta). | Two diffractometers modelled as plain devices with the config's axis maps; the circle roles are partial. | The circle geometry, which decides the `Assembly(Diffractometer)` slot shape (see [Model](#deliberately-not-here-yet)). |
| DIFF-2 | Blocks-go-live | The reciprocal-space coordination: is hklpy2 driving an (h, k, l, energy) pseudo-axis, and over what geometry? | A reciprocal-space PseudoAxis is assumed for the Assembly design; not yet a device. | The pseudo-axis model. |

### Sample environment

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MAG-1 | Blocks-go-live | The sample magnets: the two 2 T magnets (`bmag`/`emag`) and the high-field magnet (`magnet911`) field ranges and control PVs (the 2 T magnets had no control PV in the config), and the Kepco-driven `gmag`. | Four `Magnet` Assets (catalog Family, graduated); fields and several PVs unconfirmed. | The magnet specs and handles. |
| TEMP-1 | Nice-to-have | The LakeShore 336 and 340 controllers: sensor channels and the sample stages they regulate. | Two `TemperatureController` Assets (catalog Family, presents `Regulator`) at 4-ID-G. | The temperature-controller model. |
| SAMPLE-1 | Nice-to-have | The Ventus laser at 4-ID-H: is it a pump-probe source CORA should model as a device, or only carry as a Clearance hazard? | One `Laser` Asset (catalog Family); modelling-versus-hazard is open. | The laser model or hazard treatment. |
| SAMPLE-2 | Nice-to-have | The preamplifiers, lock-in (`srs810`), and high-pressure-cell controllers (Pace `PC1`/`PC2`) are in the config but not modelled here. Which are beamline equipment versus user-brought? | Deferred as peripheral. | Whether these become Assets. |

### Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The Eiger area detector model, sensor, and frame rate. | One `Camera` Asset (`4idEiger:`); model unconfirmed. | The detector Model binding. |
| DET-2 | Nice-to-have | The SGZ Vortex (`4iddMZ0:`): is it a fluorescence / energy-dispersive point detector, and what Family fits? | Bound to the catalog `PositionMonitor` Family as a placeholder; classification unconfirmed (see `TOPO-3`). | The Vortex classification and Family. |

### Beam-position monitors and supplies

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| BPM-1 | Nice-to-have | The XBPMs, Sydor electrometers, and TetrAMM: which are true beam-position monitors versus intensity (I0) normalizers? | All bound to the graduated catalog `PositionMonitor` Family presenting the Sensor Role. | The monitor classification. |
| SUP-1 | Nice-to-have | The cryogen and process-gas supplies the magnet and low-temperature environments draw on. | Liquid helium and liquid nitrogen carried pending in the descriptor. | The Supply records. |
