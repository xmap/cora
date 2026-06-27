# Sample

*The endstation sample side: the solution positioning stack, the scanning-microbeam goniometer, and the HPLC delivery pump, plus where the fluidic delivery chain, the flow cell, and the solution Subject sit. First cut; PVs read from the `NSLS2/lix-profile-collection` startup files, carried confirm.*

This is where LIX is genuinely different from the rest of the scattering fleet, so read it closely. The other scattering beamlines mount a solid sample in the beam. LIX measures a **protein in solution**: a buffer-borne macromolecule, often an eluting peak from in-line size-exclusion chromatography, flowed through an X-ray cell. The sample side therefore has two faces, the positioning hardware (which reuses the catalog) and the fluidic delivery chain (which is mostly the seam plus the Subject / Supply / Procedure shape). The hardware is modelled in the sample stage of the [descriptor](../inventory.md); the delivery chain is described here and in [Controls](controls.md).

## The sample side at a glance

| Asset | Family | PV | What it does |
| --- | --- | --- | --- |
| `SampleStage` | `Manipulator` | `XF:16IDC-ES:Scan{Ax:XC}` | the solution-mode positioning stack: a coarse x and a z pusher (EPICS) plus the fast scan x / y (XPS trajectory); it places the flow cell in the beam (`SAMPLE-1`) |
| `ScanningGoniometer` | `Goniometer` | `XF:16IDC-ES:Scan2-Gonio{Ax:sX}` | the scanning-microbeam stack: sample x / z, tilts, a rotation, and (with the XPS rot.rY) micro-tomography of cells and tissue (`SCAN-1`) |
| `DeliveryPump` | `FlowController` | `XF:16IDC-ES{HPLC}REGEN:FLOWRATE` | the HPLC pump that flows the solution and SEC peak through the cell; binds the graduated `FlowController` Family (`FLUID-1`, `FLOW-1`) |

## Placing the sample

LIX runs two endstation modes, selected at startup, and each has its own positioning stack.

The **solution mode** uses the `SampleStage`, a positioning stack that carries a coarse x and a z pusher as EPICS motors, with the fast scan x and y carried as Newport-XPS trajectory axes. It places the X-ray flow cell at the focus. It reuses the catalog `Manipulator` Family, the same multi-axis sample-positioning anatomy the soft-X-ray beamlines SIX and ESM earned, so LIX adds no device here. Which axes are EPICS and which are XPS trajectory, and how the flow cell mounts, is `SAMPLE-1`.

The **scanning-microbeam mode** uses the `ScanningGoniometer`, a SmarAct stack with sample x / z translations, tip / tilt, and a rotation axis. With the XPS `rot.rY` trajectory axis it performs micro-tomography; the fast raster axes (the XPS `scan.X` / `scan.Y`) sweep the microbeam across a cell or tissue section for mapping. It reuses the catalog `Goniometer` Family. The raster and tomo axes live on the Newport XPS trajectory controller, the motion-controller seam, and are carried as settings rather than separate Assets (`SCAN-1`).

## Delivering the solution: the fluidic chain

The fluidic sample-delivery chain is what makes LIX a solution beamline, and it is the one genuinely-new axis this deployment brings. CORA models it the way the [MX3](../../mx3/index.md) deployment modelled its non-EPICS hardware: as a heterogeneous control plane, with the interface named and the actuators placed where they belong, not forced into device vocabulary they do not earn.

**The delivery pump is the one device.** The `DeliveryPump` drives the solution and SEC-SAXS flow: a flowrate setpoint and readback, a pressure readback, and run / stop. It is heterogeneous underneath, a pcaspy soft-IOC (`XF:16IDC-ES{HPLC}`) fronts an Agilent quaternary pump driven over the OpenLAB .NET SDK on a Windows host and a regeneration pump driven over a raw TCP socket to a Moxa terminal server, but its CORA-facing anatomy is a settable flow actuator presenting `Regulator`. That is exactly the graduated catalog `FlowController` Family, the settable-actuator sibling of `TemperatureController` that i22 and 7-BM also use. So the pump **reuses** the graduated `FlowController`; it coins nothing. LIX is one of the four consumers (i22, 7-BM, LIX, XFP) that earned the graduation (see [Model](../model.md#the-graduated-flowcontroller-family)).

**The rest of the chain is the seam plus Subject / Supply / Procedure**, not devices:

| Part of the chain | How CORA models it | Why |
| --- | --- | --- |
| The VICI and Aurora selector valves | the ControlPort seam (`FLUID-1`) | discrete N-position routers (column, buffer, detector selection) over Moxa TCP sockets, with no existing Family; CORA conducts them over the seam, coining no Valve Family at n=1 |
| The size-exclusion column and buffers | Supply consumables (`SEC-1`) | a column is chosen per sample (a config / consumable, not a device); buffers are selected on the Aurora valve |
| The X-ray flow cell | sample environment (`SEC-1`, `FLUID-1`) | the cell lives in an external library (lixtools); its positions are config, not catalog devices here |
| The sample-handling robot and the autosampler | a Procedure + a Subject custody thread (`ROBOT-1`) | the task-verb-driven robot (the `SW:` method soft-IOC) and the Agilent autosampler fold to a Procedure over the spine, the i03 / MX3 robot precedent, not a device Family |
| The solution sample / eluting peak | a Subject (`SUBJECT-1`) | the thing measured is a liquid macromolecule or a chromatographic peak, with its own provenance, distinct from a solid mount |

## The solution Subject and the SEC-SAXS Procedure

The deepest novelty is not hardware at all. For SEC-SAXS, what gives the experiment its identity in CORA's record is the **Subject** (which protein, which buffer, which eluting peak), the **Supply** (which column, which buffers, the needle wash), and the **Procedure** (purge, equilibrate, inject, flow-during-exposure, fraction). The HPLC pump and valves are the actuators that Procedure drives over the `ControlPort`; the elution profile is the acquisition axis, with the SAXS frames correlated to the chromatographic peak. CORA owns the Subject, the Supply, and the Procedure as its system-of-record concern; it conducts the fluidic actuators over the seam (`FLUID-1`, `SEC-1`, `SUBJECT-1`). These aggregates are not instantiated in this descriptor-and-docs cut; they are the shape the deployment will take, recorded so the reader knows where the solution experiment lives.

## Sample environment

The sample-cell temperature controllers, an AccuThermo FTC100D and an SMC chiller, have their module-level instances **commented out** in the profile collection (a solution mode instantiates an FTC100D), so this is a scope deferral rather than a clean absence: no temperature-controller device is modelled in this cut, and the in-situ temperature environment is carried pending (`TEMP-1`). The one temperature mirrored to a PV is the autosampler thermostatted-tray temperature (`SAMPLER:TEMP`), part of the fluidic seam and folded into the same deferral.

## Why no new Family here

The positioning hardware reuses the catalog throughout: `Manipulator` for the solution stack, `Goniometer` for the scanning stage. The one fluidic device, the delivery pump, reuses the graduated catalog `FlowController` Family rather than coining a new one. The selector valves, the column, the flow cell, the robot, and the solution sample are deliberately not coined as device Families: they are the seam plus the Subject / Supply / Procedure shape, which is where a solution beamline's novelty belongs (`FLUID-1`, `SEC-1`, `ROBOT-1`, `SUBJECT-1`). LIX coins no new Family here.

See [Open questions](../questions.md) for the sample-side facts still to confirm, [Inventory](../inventory.md) for the Asset tree, [Model](../model.md) for the family-reuse rationale and the graduated FlowController Family, and [the source walk](../beamline.md) for the PVs as read from the profile collection.
