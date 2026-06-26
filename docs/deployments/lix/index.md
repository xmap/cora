# LIX

*The Life Science X-ray scattering beamline at NSLS-II, beamline 16-ID: the structure of biological macromolecules in solution by small- and wide-angle scattering (bio-SAXS / WAXS), including in-line size-exclusion chromatography (SEC-SAXS), plus a scanning-microbeam endstation for cells and tissue. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `LIX` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 16` (PV namespace `XF:16ID*`; not a registered Asset) |
| Status | First cut, reverse-engineered, design-phase (descriptor + docs; scenarios deferred) |
| Source | An in-vacuum undulator (`SRC-1`) |
| Control stack | NSLS-II EPICS / ophyd plus a heterogeneous fluidic control plane (a Moxa terminal server, the Agilent OpenLAB .NET SDK, and a pcaspy soft-IOC); handles bound from the profile collection, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/lix-profile-collection](https://github.com/NSLS2/lix-profile-collection)). EPICS PVs are real and read from the `startup/` files; vendor part numbers, serials, and physical positions are not in the profile collection and are open questions. Every value is carried as `confirm` until LIX staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes LIX different

Be precise about where the novelty is. LIX's measurement, small- and wide-angle X-ray scattering, is a science axis the fleet already speaks: it overlaps the materials-scattering beamlines [SMI](../smi/index.md), [CMS](../cms/index.md) (12-ID and 11-BM), Diamond [I22](../i22/index.md), and APS [9-ID](../9-id/index.md) / [12-ID-E](../12-id-e/index.md). The detectors, the optics, and the beam path reuse the catalog throughout and coin nothing. What is genuinely new at LIX is **above the detector and beside the sample**: the **Subject** and the **sample-delivery chain**.

LIX is the fleet's first **life-science solution-scattering** beamline. The specimen is not a solid mounted in the beam; it is a protein in liquid, often an eluting peak from in-line size-exclusion chromatography (SEC-SAXS), delivered by an HPLC fluidic chain through a flow cell. So the contributions that matter for CORA are:

- **The solution Subject.** The thing measured is a buffer-borne macromolecule (or a chromatographic peak), a liquid sample with its own provenance, distinct from every solid mount the fleet has modelled (`SUBJECT-1`).
- **The fluidic sample-delivery chain.** An HPLC delivery pump, selector valves, a size-exclusion column, buffers, and a flow cell move the sample into the beam in lockstep with the exposure. This is the fleet's first fluidic delivery plane, and it is heterogeneous: mostly non-EPICS (a Moxa terminal server, the Agilent OpenLAB .NET SDK, a pcaspy soft-IOC), the same shape the [MX3](../mx3/index.md) deployment established for non-EPICS hardware (`FLUID-1`).
- **The SEC-SAXS Procedure.** Purge, equilibrate, inject, flow-during-exposure, and fraction: the run is a flow program correlated to the elution, a Procedure over the seam rather than a device (`FLUID-1`, `SEC-1`).

LIX coins **no new Family**, and the one reuse worth naming is the HPLC delivery pump, which binds the graduated catalog `FlowController` Family (one of the four consumers, i22 / 7-BM / LIX / XFP, that earned its graduation; see below). The catalog is otherwise unchanged. Frame the rest of these docs around the Subject and the delivery chain, and read the scattering itself as the fleet shape ported once more.

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics (`XF:16IDA`, `XF:16IDB`) | Yes | The undulator, the DCM and beam-energy axis, the white-beam and KB mirrors, the mono slit and secondary-source aperture, the photon and fast shutters (`ENC-1`) |
| Endstation optics (`XF:16IDC`) | Yes | The compound refractive lens transfocator and the guard slit |
| Endstation (`XF:16IDC`) | Yes | The solution positioning stack, the scanning-microbeam goniometer, the HPLC delivery pump, the SAXS / WAXS detectors, the fluorescence spectrometer, the detector stage, the beamstop, the flux and beam-position monitors, the Zebra trigger (`ENC-1`) |
| New device classes | None | Zero new Families coined in this scaffold; the catalog is unchanged here |
| The HPLC delivery pump | Graduated `FlowController` | Binds the graduated catalog flow / pump-actuator Family (presents Regulator; earned across i22 / 7-BM / LIX / XFP) (`FLUID-1`, `FLOW-1`) |
| Selector valves, SEC column, flow cell, sample robot | Seam + Subject / Supply / Procedure | The fluidic-routing valves are the ControlPort seam; the column and buffers are Supply; the robot is a Procedure; the solution is a Subject. None is a device Family (`FLUID-1`, `SEC-1`, `ROBOT-1`, `SUBJECT-1`) |
| The attenuator and the cell temperature controllers | No (disabled in source) | The attenuator and both temperature controllers are commented out in the profile collection; not invented (`ATTN-1`, `TEMP-1`) |
| Integration scenarios + vendor Models | No | Design-phase; the descriptor and docs come first |

The deferred parts are recorded on [Model](model.md).

## Key modelling decisions

- **Reuse over coin.** Every device binds an existing catalog or loose Family, and this scaffold changes nothing in the catalog. The novelty lands on Subject, Supply, and Procedure, not on device vocabulary.
- **16-ID is an undulator beamline, so it carries an `InsertionDevice`.** Unlike the bending-magnet [CMS](../cms/index.md), LIX has an in-vacuum undulator on the spine, observed alongside the loose `StorageRing`; the device model and period are carried pending (`SRC-1`, `MACHINE-1`).
- **The HPLC delivery pump reuses the graduated `FlowController` Family.** A settable flow / pump actuator presenting `Regulator`, it binds the catalog Family (the settable-actuator sibling of `TemperatureController`) that graduated on the rule-of-three across i22, 7-BM, LIX, and XFP. LIX is one of the four consumers that earned the graduation (`FLUID-1`, `FLOW-1`).
- **The fluidic chain is the seam plus Subject / Supply / Procedure.** The selector valves (no existing Family) stay in the ControlPort seam; the SEC column and buffers are Supply consumables; the sample robot and autosampler are a Procedure over the spine with a Subject custody thread (the i03 / MX3 robot precedent); the liquid sample is a Subject. None is coined as a device Family (`FLUID-1`, `SEC-1`, `ROBOT-1`, `SUBJECT-1`).
- **The compound refractive lens reuses the graduated `Transfocator`.** The Transfocator Family is well established across the fleet (the APS / Diamond CRLs and the NSLS-II siblings CHX / IXS / SMI / FMX); LIX adds another consumer, not a new abstraction (`CRL-1`).
- **Zero new Families coined in this scaffold; the catalog is unchanged here.**

## The beamline

- [Source](beamline.md): the generated device walk: the storage-ring machine state, the in-vacuum undulator, the double-crystal monochromator and the beam-energy pseudo-axis over its Bragg angle, the white-beam and KB mirrors, the mono slit and secondary-source aperture, the photon and fast shutters, and the endstation transfocator and guard slit.
- [Sample](equipment/sample.md): the solution positioning stack, the scanning-microbeam goniometer, and the HPLC delivery pump, plus where the fluidic delivery chain, the flow cell, and the solution Subject sit.
- [Detector](equipment/detector.md): the SAXS and WAXS Pilatus detectors, the scanning-mode fluorescence spectrometer, the detector translations, the SAXS beamstop, the endstation flux monitors, and the beam-position monitor.

Cutting across them:

- [Controls](equipment/controls.md): the EPICS / ophyd control stack, the heterogeneous fluidic control plane, and the bluesky-orchestration seam; handles bound from the profile collection and carried confirm (`CTRL-1`).

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/lix/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of LIX is designed to do, as intent. Biological solution scattering (bio-SAXS / WAXS) and SEC-SAXS map to a new `solution_scattering` Method; the scanning-microbeam mode reuses the pending `scanning_fluorescence_microscopy` Method. All render unlinked, carried pending (`TECH-1`).

## Governance

[Governance](governance.md): who will act at LIX and the trust shape that gates their commands. People and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here), surfacing through their actions and gated by a Zone-plus-Conduit-plus-Policy trust shape. The NSLS-II operator pool and review are pending at the Site (`GOV-1`). The profile collection's security model is a POSIX-ACL login, not a PSS integration, so the search-and-secure permit signals and shutters are absent and carried pending, not invented (`PSS-1`).

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's LIX content lives, and the record of what is deliberately deferred. LIX introduces no new Family.

## Not yet documented

LIX is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS search-and-secure permit signals and shutters are absent from the profile collection and are not invented here (`PSS-1`).
