# Model

*The developer's index into where LIX content lives, why this deployment coins no new family, how it models a solution beamline's fluidic delivery without inventing device vocabulary, and the record of what is deliberately deferred. First cut.*

LIX is a descriptor-and-docs scaffold today, reverse-engineered from the beamline's profile collection: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/lix/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/lix/beamline.yaml) | the device walk with bound PVs; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/nsls2/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/nsls2/site.yaml) | the NSLS-II facility surface; `LIX` added to its beamline list, with solution-scattering / SEC-SAXS / scanning Practices |
| Extraction provenance | [NSLS2/lix-profile-collection](https://github.com/NSLS2/lix-profile-collection) | the `startup/` device definitions the descriptor was curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none coined; every device reuses an existing catalog or loose Family (below), including the now-graduated `FlowController` |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; `solution_scattering` is a new pending slug and `scanning_fluorescence_microscopy` is reused pending (`TECH-1`) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers LIX Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes LIX new

The honest answer is: not the detector, and one real thing on the sample side. LIX measures biological structure by small- and wide-angle X-ray scattering (bio-SAXS / WAXS), in-line size-exclusion-chromatography-coupled scattering (SEC-SAXS), and scanning-microbeam mapping. The scattering hardware overlaps the fleet heavily: LIX shares its science axis and its `Camera` / `FluxMonitor` / `BeamStop` vocabulary with the materials-scattering beamlines SMI, CMS, I22, and 9-ID, and contributes reinforcement there, not novelty.

LIX's genuinely distinct contributions are above the detector and beside the sample:

- **The solution Subject.** The fleet's first life-science solution-scattering beamline measures a buffer-borne macromolecule, often an eluting chromatographic peak, rather than a solid mount. That is a new Subject shape, with its own provenance, not a new device (`SUBJECT-1`).
- **The fluidic sample-delivery chain.** An HPLC delivery pump, selector valves, a size-exclusion column, buffers, and a flow cell move the sample into the beam in lockstep with the exposure. It is the fleet's first fluidic delivery plane, and it is heterogeneous (a Moxa terminal server, the Agilent OpenLAB .NET SDK, a pcaspy soft-IOC), the MX3 non-EPICS shape extended to fluidics (`FLUID-1`).
- **The SEC-SAXS Procedure.** The run is a flow program correlated to the chromatographic elution, a Procedure over the seam plus a Subject / Supply shape, not a device (`FLUID-1`, `SEC-1`).

## No new families

LIX coins no new Family and changes nothing in the catalog.

- **16-ID is an undulator beamline** (unlike the bending-magnet CMS), so it carries an `InsertionDevice` on the spine; the machine state is also observed through the loose `StorageRing`, and the undulator detail is `SRC-1`.
- **The DCM binds `Monochromator`** (a silicon double-crystal optic, the energy law implies Si(111)); the incident energy is a `PseudoAxis` over its Bragg angle and the undulator gap.
- **The optics and detectors all reuse:** the white-beam and KB mirrors bind `Mirror`; the slits bind `Slit`; the compound refractive lens binds the graduated `Transfocator`; the shutters bind `Shutter`; the solution positioning stack binds the graduated `Manipulator`; the scanning goniometer binds `Goniometer`; the Pilatus detectors bind `Camera`; the Xspress3 binds the graduated `EnergyDispersiveSpectrometer`; the detector translations bind `LinearStage`; the beamstop binds `BeamStop`; the TetrAMM electrometers bind `FluxMonitor`; the diamond-diode / Best beam-position monitor binds the loose `BeamPositionMonitor` (held under review, `DIAG-1`); the Zebra binds `TimingController`.

## The graduated FlowController Family

The one reuse worth spelling out is the HPLC delivery pump. Its CORA-facing anatomy is a settable flow / pump actuator presenting `Regulator`: a flowrate setpoint and readback, a pressure readback, and run / stop. That is exactly the graduated catalog `FlowController` Family, the continuous-setpoint flow / pump actuator that presents `Regulator` and is the settable-actuator sibling of `TemperatureController`. So the pump **reuses** the graduated `FlowController`; it coins nothing.

`FlowController` graduated into the catalog on the rule-of-three across Diamond i22, APS 7-BM, NSLS-II LIX, and NSLS-II XFP, the same way `TemperatureController`, `FluxMonitor`, and `EmissionSpectrometer` did: presenting the existing `Regulator` Role, so a YAML-and-docs change with no new Role or affordance. LIX is one of the four consumers that earned the graduation, and it now simply **binds the catalog `FlowController` Family (graduated; presents `Regulator`)**. The wider fluidic chain stays deferred (`FLUID-1`, `FLOW-1`).

## How the fluidic chain is modelled (mostly not a device)

The fluidic delivery chain is the novel axis, and only one piece of it is a device:

- the **delivery pump** is the `DeliveryPump`, binding the graduated `FlowController` (above);
- the **selector valves** (VICI column / purge / detector, the Aurora buffer valve) are the ControlPort **seam**: discrete N-position routers over Moxa TCP sockets, with no existing Family, conducted over the seam and not coined at n=1 (`FLUID-1`);
- the **SEC column and buffers** are **Supply** consumables (`SEC-1`);
- the **flow cell** is sample environment, living in an external library (lixtools), not a catalog device here (`SEC-1`, `FLUID-1`);
- the **sample robot and autosampler** are a **Procedure** over the spine plus a **Subject** custody thread, the i03 / MX3 robot precedent, not a device Family (`ROBOT-1`);
- the **solution sample / eluting peak** is a **Subject** (`SUBJECT-1`).

This is the CORA-lens decision for a solution beamline: the experiment's identity lives in the Subject (which protein, which peak), the Supply (which column, which buffers), and the Procedure (the flow program), with the pump and valves as actuators conducted over the seam. Coining `Pump` and `Valve` device Families at n=1 would mint federation vocabulary one deployment cannot earn alone; the pump reuses the graduated `FlowController` Family instead, and the valves stay in the seam pending a second fluidic beamline (`FLUID-1`).

## Deliberately not here yet

- **The selector-valve Family (`FLUID-1`).** The VICI and Aurora valves are discrete-position routers with no existing Family. Per earn-the-abstraction they are carried in the seam at n=1, no `Valve` / `SelectorValve` Family coined; a second fluidic beamline would earn the abstraction.
- **The disabled attenuator and the deferred temperature controllers.** The `Fltr:Attn` attenuator and its lookup tables are commented out in the profile collection, so no attenuator is modelled, not invented (`ATTN-1`). The sample-cell temperature controllers (the FTC100D and the SMC chiller) have their module-level instances commented out, though a solution mode instantiates an FTC100D, so this is a scope deferral; the autosampler tray temperature (`SAMPLER:TEMP`) is folded into the same deferral (`TEMP-1`).
- **The Methods.** Whether `solution_scattering` and the scanning Method enter CORA's catalog is an owner decision; the Practices render unlinked, pending. `solution_scattering` is new and `scanning_fluorescence_microscopy` is reused pending (`TECH-1`).
- **The multi-mode endstation rebinding.** The solution, scanning, and vacuum-scan modes rebind the logical sample axes across physical PVs and controllers (EPICS, XPS trajectory, SmarAct) at startup; CORA models the logical stacks and carries the active binding as a setting (`SAMPLE-1`, `SCAN-1`), not as separate Assets.
- **The third Pilatus, the Kinetix, and the viewing cameras.** The 300K WAXS1 head is disabled, the Xspress3 is optional, and the Kinetix and Prosilica cameras are not modelled in this cut (`DET-1`).
- **The simulated devices and full asset-tree scenarios.** No `test_lix_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
