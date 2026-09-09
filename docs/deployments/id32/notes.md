# Notes

## Techniques

*What the modelled part of ID32 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../esrf/index.md#the-techniques-adapted-here) is how a facility adapts it. ID32 runs three soft X-ray techniques, all new to CORA's catalog, so the Methods below render unlinked and are carried pending until a technique enters scope (`TECH-1`).

### Resonant inelastic X-ray scattering, magnetic dichroism, emission

ID32 sets the X-ray energy and polarization with the twin APPLE-II undulators and the plane-grating monochromator, then either disperses the inelastically scattered beam on a long spectrometer arm (RIXS), or measures the absorption asymmetry between polarizations in a high magnetic field (XMCD), or disperses the emitted beam (XES).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Resonant inelastic X-ray scattering | `resonant_inelastic_scattering` | the roughly 5 m dispersive [spectrometer arm](detector.md) on the RIXS endstation, scanned in energy against the [incident-energy axis](source.md); reuses the SIX RIXS Method, the second consumer; Method not yet in the catalog |
| X-ray magnetic dichroism | `xmcd` | absorption asymmetry in the 9 T [XMCD magnet](sample.md) between circular / linear polarizations set on the [APPLE-II](source.md); reuses the 4-ID / i06 / i10 dichroism Method; pending |
| X-ray emission spectroscopy | `xas_spectroscopy` | the [XES Rowland arm](detector.md) at the XMCD endstation; reuses the `xas_spectroscopy` Method that ISS / LCLS-MFX left pending for XES; pending |

RIXS needs the [incident-energy and polarization axes](source.md), the [RIXS diffractometer](sample.md) to set the scattering geometry, and the [dispersive spectrometer arm and its CCD](detector.md). XMCD needs the polarization axis, the [9 T magnet and its VTI](sample.md), and a detection channel. XES needs the [emission spectrometer arm](detector.md).

### A new operating axis for the fleet, on familiar vocabulary

RIXS at ID32 is the fleet's second soft X-ray RIXS after SIX, and the dispersive spectrometer arm is the device that ties them together: the same `SpectrometerArmsController` anatomy that SIX coined loose, sighted three times across two sites (the ID32 RIXS arm, the ID32 XES arm, and SIX). That rule-of-three earned the graduation of the `SpectrometerArm` Family, which has since landed as a catalog Family (SIX + ID32 RIXS/XES + ID28; see [Model](#loose-families-brought-to-a-rule-of-three-all-since-graduated)). XMCD and XES likewise reuse the dichroism and emission Methods the fleet already carries pending; none forces a new device family.

### Not modelled yet

The concrete acquisition recipes (the RIXS energy maps and arm alignment, the XMCD field-and-polarization sequences, the XES scans, and the counting times) are not written yet; they join as the deployment approaches the point where CORA drives ID32. Whether RIXS, XMCD, and XES enter CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at ID32, and the trust shape that will gate it. First cut.*

Governance at ID32 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [ESRF Site](../esrf/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

ID32 is CORA's first ESRF deployment, so the ESRF is a brand-new Site: the operator pool and the safety-review structure are carried pending on the [ESRF Site](../esrf/index.md#safety-and-governance), shared across the facility's beamlines, until ESRF staff confirm them (`GOV-1`). ID32 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives ID32, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The ESRF personnel-safety permit signals and the photon and front-end shutters are absent from the BLISS Beacon config, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [ESRF Site](../esrf/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

ID32 adds the hazard classes that come with its endstations: a 9 Tesla superconducting magnet and its liquid-helium cryogen plant at the XMCD endstation, and an intense polarized soft X-ray beam. Those land with the instruments that bring them, and an experiment Clearance would carry them; the magnet and its cryogens are modelled as hazards on the experiment, not as Assets CORA drives for safety (the LASER-1 / sample-environment precedent).

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives ID32, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's ID32 content lives, the graduations it earns, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at ID32 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (the polarization PseudoAxis) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes ID32 new

ID32 is two things the fleet has not had: a new Site and a new controls house-style. It is CORA's **seventh Site** (the ESRF, Grenoble), the biggest re-test of the Site and Federation kernel a single deployment can be, and the **first BLISS / Beacon / Tango / IcePAP** control plane CORA models (the rest are EPICS, or Tango / Sardana at MAX IV). Its science is soft X-ray resonant inelastic scattering (RIXS) with a ~5 m dispersive spectrometer arm, and X-ray magnetic dichroism (XMCD) plus X-ray emission spectroscopy (XES) at a 9 Tesla high-field-magnet endstation, all fed by twin APPLE-II undulators through a soft X-ray plane-grating monochromator.

ID32 coins no new Family. The twin APPLE-II undulators bind the catalog `InsertionDevice`, and the polarization is a `PseudoAxis` over the undulator phase, exactly as i06 and i10 modelled their APPLE-II sources; the PGM binds `GratingMonochromator`; the 4-circle diffractometer binds `Goniometer` with a reciprocal-space `PseudoAxis` (the Assembly named, not built, DIFF-1 / DIFF-2); the Andor CCDs bind `Camera`; the LakeShore VTI and coil-diagnostic controllers bind `TemperatureController`; the XMCD sample stage binds `LinearStage`; the machine state binds the loose `StorageRing`.

### Loose families brought to a rule-of-three (all since graduated)

ID32 pushed three loose families to a genuine rule-of-three. Per the owner decision (2026-06-27) each graduation is a dedicated, gated catalog PR rather than bundled into this scaffold; all three have since **graduated**.

| Loose family | Sightings with ID32 | ID32 binding | Status |
| --- | --- | --- | --- |
| `SpectrometerArm` | SIX + ID32 RIXS arm + ID32 XES arm + ID28 | the two dispersive spectrometer arms (the same `SpectrometerArmsController` class instantiated twice) | **graduated**: earned across SIX + ID32 RIXS/XES + ID28; presents the `Positioner` Role |
| `Magnet` | 4-ID + i10-1 + ID32 | the 9 T / 4 T XMCD split-coil magnet | **graduated**: earned across 4-ID + i10-1 + ID32; presents the `Regulator` Role, the field a settable process variable (`MAG-1` now covers only the per-Asset field detail) |
| `PolarizationAnalyzer` | 4-ID + i10 + ID32 + P09 | the RIXS scattered-beam polarimeter | **graduated** (`POL-2`): catalog Family across 4-ID / i10 / ID32 / P09, presents Positioner |

Keeping each graduation as its own PR keeps the scaffold clean and lets each get its own naming-r3 and gate-review. `SpectrometerArm` was the clearest: it presents the `Positioner` Role (an arm that positions a grating and carries a `Camera` at its focus), which is exactly why it never fit the point-Sensor families (`FluxMonitor` / `EnergyDispersiveSpectrometer`) and was coined loose at SIX.

### The BLISS / Tango control plane

ID32 is the first non-EPICS, non-Sardana controls house-style in the fleet: BLISS / Beacon (a YAML device database) over Tango and IcePAP. CORA models the control handles as opaque edge strings regardless of transport, the way the MX3 heterogeneous-control precedent does: a Tango device URL (`id32/limaccds/andor_1`), an IcePAP host+address (`iceid324`), or a BLISS axis name is the handle, carried confirm (`CTRL-1`). The RIXS / XMCD / XES acquisition runs through BLISS sequences; that orchestration is the seam CORA's edge replaces, conducting over Tango / IcePAP rather than replacing BLISS.

### Deliberately not here yet

- **The graduations (`RIXS-1`, `MAG-1`, `POL-2`).** All three families ID32 brought to a rule-of-three, `SpectrometerArm`, `Magnet`, and `PolarizationAnalyzer`, have since graduated into the catalog via their dedicated gated PRs.
- **The exact optics handles (`MONO-1`, `OPT-1`, `OPT-2`, `DIFF-1`, `SAMPLE-1`).** The PGM, mirrors, slits, diffractometer axes, and XMCD sample stage are carried confirm-pending; the decision-critical devices (the arms, the magnet, the LakeShores, the CCDs, the undulator) carry their real BLISS addresses.
- **The Assembly(Diffractometer) and the reciprocal-space rule (`DIFF-1`, `DIFF-2`).** Named, not built, as the other diffractometer beamlines deferred theirs.
- **The RIXS / XMCD / XES Methods.** Whether they enter CORA's catalog is an owner decision; the Practices render unlinked, pending, reusing the SIX RIXS, the 4-ID / i06 / i10 XMCD, and the xas_spectroscopy XES slugs (`TECH-1`).
- **The simulated devices and full asset-tree scenarios.** No `test_id32_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the ID32 team to confirm before the model can be trusted.*

ID32 was reverse-engineered from the ESRF's open BLISS Beacon device database ([gitlab.esrf.fr/id32/beamline_configuration](https://gitlab.esrf.fr/id32/beamline_configuration), a git mirror of the live Beacon config), so the control handles on the [device pages](index.md) are the beamline's real Tango / IcePAP / BLISS addresses, read from the config rather than confirmed by staff. This is CORA's first ESRF Site and first BLISS / Tango / IcePAP controls house-style. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: a shared optics zone feeding the RIXS and XMCD endstations, or a different layout? | A shared `id32-optics` zone and the `id32-rixs` and `id32-xmcd` experiment hutches. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The APPLE-II undulator period and segment count. | An APPLE-II undulator source on the `id/master/id32` device server; period pending. | The source Asset detail. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The ESRF-EBS storage-ring state ID32 reads. | Observe-only machine state, a loose `StorageRing`; exact handles pending. | The machine-state observation. |
| POL-1 | Blocks-go-live | The polarization value domain (linear / circular) and the phase conversion: pin it as a Calibration or run it rule-less on the live controller? | A `PseudoAxis` over the APPLE-II phase; rule-less by default (the i06 / i10 precedent). | The polarization-axis modelling. |
| MONO-1 | Blocks-go-live | The PGM grating line densities, the cff, the incident-energy range, and the exact handles. | A soft X-ray PGM bound to `GratingMonochromator`; energy a `PseudoAxis`. | The monochromator and incident-energy Assets. |
| OPT-1 | Nice-to-have | The focusing-mirror coatings and the exact handles. | Soft X-ray focusing mirrors bound to `Mirror`. | The mirror Asset detail. |
| OPT-2 | Nice-to-have | The beam-defining slit blade-axis map and handles. | Slits bound to `Slit`. | The slit Asset detail. |

### RIXS endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-go-live | The 4-circle diffractometer (BLISS `DiffE4CH`, E4CH) circle roles and axes. | A `Goniometer`; the `Assembly(Diffractometer)` is named, not built. | The diffractometer geometry; the CORA structural modelling is on [Model](#deliberately-not-here-yet). |
| DIFF-2 | Nice-to-have | The reciprocal-space (hkl) coordination over the diffractometer. | A reciprocal-space `PseudoAxis`, the rule deferred. | The reciprocal-space Asset. |
| RIXS-1 | Blocks-go-live | The RIXS and XES dispersive spectrometer arms (the `SpectrometerArmsController` geometry, the Rowland radii, the grating modes). | Both bind the catalog `SpectrometerArm` Family (graduated across SIX + ID32 RIXS/XES + ID28); the per-Asset arm geometry stays pending. | The spectrometer-arm geometry; the family graduation is settled (see [Model](#loose-families-brought-to-a-rule-of-three-all-since-graduated)). |
| POL-2 | Nice-to-have | The RIXS scattered-beam polarimeter (the `thpol` / `chipol` / `tthpol` block). | Binds the catalog `PolarizationAnalyzer`, graduated across 4-ID / i10 / ID32 / P09. | The polarimeter modelling. |
| DET-1 | Blocks-go-live | The Andor CCD configurations (RIXS `andor_1`, XES `andor_2`). | Both bind `Camera`. | The detector modelling. |

### XMCD endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MAG-1 | Blocks-go-live | The 9 T / 4 T XMCD split-coil magnet (field range, ramp, the two coils) and its cryogen plant. | Binds the catalog `Magnet` Family (graduated across 4-ID + i10-1 + ID32); the field is a settable axis (Regulator), the per-Asset field detail pending. | The per-Asset magnet field / control detail; the family graduation is settled (see [Model](#loose-families-brought-to-a-rule-of-three-all-since-graduated)). |
| TEMP-1 | Nice-to-have | The LakeShore 336 (VTI sample) and 340 (coil / shield diagnostics) sensor and loop maps, and the He needle valve. | Two `TemperatureController` Assets presenting the `Regulator` Role; the needle valve folds into the VTI. | The temperature-control modelling. |
| SAMPLE-1 | Blocks-go-live | The XMCD sample-positioning stage axes inside the magnet bore. | A `LinearStage`; axis set pending. | The sample-stage modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the Tango / IcePAP / BLISS handles read from the public Beacon config current and correct? | The handles in the descriptor are taken from the BLISS config and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The ESRF personnel-safety permit signals and the photon / front-end shutters (absent from the BLISS config). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the liquid-helium supply for the magnet. | Photon beam, cooling water, vacuum, and liquid helium. | The Supply observations. |
| GOV-1 | Nice-to-have | The ESRF operator pool and safety-review structure (site-level). | Carried pending on the ESRF Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Do RIXS, XMCD, and XES enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the SIX RIXS, the 4-ID / i06 / i10 XMCD, and the xas_spectroscopy XES slugs; none coined. | The technique Capabilities. |
