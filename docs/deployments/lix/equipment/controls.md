# Controls

*The control stack, the heterogeneous fluidic control plane, and the bluesky-orchestration seam. First cut; handles read from the profile collection, carried confirm.*

LIX runs on the NSLS-II EPICS / ophyd control stack, the same floor as FXI, HXN, SRX, BMM, SIX, CHX, ESM, SMI, and CMS, plus a heterogeneous fluidic control plane on a separate HPLC cart. CORA observes that floor and, where it replaces bluesky-style orchestration, conducts over it; it does not replace EPICS itself.

## Device handles

The EPICS control handles are filled from the beamline's own bluesky profile collection ([NSLS2/lix-profile-collection](https://github.com/NSLS2/lix-profile-collection), the `startup/components` and `startup/devices` files), so the descriptor carries the real PV roots and per-axis maps. The optics zone (XF:16IDA, with the transport zone XF:16IDB) carries the monochromator (`XF:16IDA-OP{Mono:DCM-Ax:Bragg}`, `MONO-1`) and the undulator (`SR:C16-ID:G1{IVU:1}`, `SRC-1`); the endstation zone (XF:16IDC) carries the sample stacks (`XF:16IDC-ES:Scan`, `SAMPLE-1`), the transfocator (`XF:16IDC-OP{CRL}`, `CRL-1`), and the area detectors (`XF:16IDC-DT{Det:SAXS}`, `XF:16IDC-DT{Det:WAXS2}`, `DET-1`). They remain confirm-pending: a value read from the profile collection is evidence to verify with staff, not a CORA-owned fact (`CTRL-1`).

Motion is split across controllers. A Newport XPS trajectory controller drives the fast scan and tomo axes (`scan.X` / `scan.Y` / `rot.rY`); a SmarAct controller drives the scanning goniometer; Delta-Tau racks drive other stages. The Zebra generates the detector triggers, gated from the XPS (`TRIG-1`). The XPS and SmarAct are non-EPICS in part, conducted over the seam like the fluidics below.

## The heterogeneous fluidic control plane

This is the part that sets LIX apart, and CORA models it the way the [MX3](../../mx3/index.md) deployment modelled its non-EPICS hardware: as a control plane that spans several transports, with each actuator placed where it belongs rather than forced into device vocabulary. The fluidic chain runs on a separate HPLC cart with its own Moxa terminal server.

| Fluidic element | Transport | How CORA models it |
| --- | --- | --- |
| HPLC delivery pump (Agilent quaternary + regeneration) | the Agilent OpenLAB .NET SDK (Windows host) and a raw TCP socket to the Moxa, fronted by a pcaspy soft-IOC (`XF:16IDC-ES{HPLC}`) | the `DeliveryPump` device, binding the graduated catalog `FlowController` Family (presents Regulator; earned across i22 / 7-BM / LIX / XFP) (`FLUID-1`, `FLOW-1`) |
| VICI selector valves (column / purge / detector) | Moxa TCP sockets, no EPICS | the ControlPort seam; N-position routers with no existing Family, not coined (`FLUID-1`) |
| Aurora Pro buffer valve | serial over a Moxa socket, mirrored to the soft-IOC (`Buffer_VALVE_POS`) | the seam; the chosen position is observed via the soft-IOC (`FLUID-1`) |
| SEC column and buffers | configuration / consumable | Supply consumables (`SEC-1`) |
| X-ray flow cell | an external library (lixtools) | sample environment, not a device here (`SEC-1`, `FLUID-1`) |
| sample robot and autosampler | the `SW:` method soft-IOC and the Agilent autosampler | a Procedure over the spine plus a Subject custody thread (`ROBOT-1`) |

Only the delivery pump is promoted to a device; the rest is the seam plus the Subject / Supply / Procedure shape. The valves' discrete-routing semantics, the column choice, and the robot's task verbs are conducted over the `ControlPort` during a run, but none earns a device Family at this cut (`FLUID-1`).

## The orchestration seam

The LIX acquisition runs through bluesky plans: the SAXS / WAXS exposures, the scanning-microbeam raster, and the SEC-SAXS flow program. The data plane publishes documents to Kafka with run metadata in Redis and a custom HDF packing queue; there is no Tiled and no queueserver in the profile collection (`CTRL-1`). That orchestration is the seam CORA's edge replaces: CORA conducts the run over the `ControlPort`, driving through ophyd / EPICS and the fluidic transports rather than replacing them. The area-detector file-writing to the NSLS-II filestore is plumbing CORA observes, not data it owns; CORA keeps its own data-of-record (see [Model](../model.md)).

What CORA conducts over the floor, by leg:

| Floor activity (bluesky today) | CORA leg | Devices / actuators conducted |
| --- | --- | --- |
| SAXS / WAXS exposure | acquisition over `ControlPort` | Camera (the Pilatus heads), BeamStop, FluxMonitor, the Zebra trigger |
| Scanning-microbeam raster + tomo | acquisition over `ControlPort` | the scanning Goniometer, the XPS trajectory axes, the fluorescence spectrometer |
| SEC-SAXS flow program | a Procedure over `ControlPort` | the DeliveryPump (FlowController), the selector valves (seam), the SAXS Camera, the FluxMonitor |
| Sample mount / exchange | a Procedure | the robot and autosampler (seam), a Subject custody thread (`ROBOT-1`) |
| Frames to the NSLS-II filestore | observed plumbing | none owned; CORA moves frames into its own Dataset of record |

### The SEC-SAXS run specifically

Specular solution scattering with in-line chromatography is the loop worth spelling out. CORA equilibrates the column (the DeliveryPump flowrate over the FlowController, the buffer chosen on the Aurora valve), injects the sample, and then reads SAXS frames continuously while the peak elutes through the cell, correlating each frame to the elution profile and normalizing on the FluxMonitor. The Subject is the eluting peak; the column and buffers are Supply; the flow is the Procedure. CORA conducts the pump and valves over the `ControlPort` rather than leaving the HPLC cart to own the loop, and records the Subject / Supply / Procedure / Dataset as its system of record (`FLUID-1`, `SEC-1`, `SUBJECT-1`).

## Equipment protection

The personnel PSS search-and-secure permit signals, the front-end and photon shutters, and any equipment-protection interlock tier are absent from the profile collection (its security model is a POSIX-ACL login, not a PSS integration); only the photon-shutter enable status is present, and the rest is not invented here (`PSS-1`). If CORA later models the protection tier, it would not model the interlock logic itself; it would only observe outcomes, mapping the in-situ environments (the vacuum optics and flight path) to Supply and Asset condition. That mapping is not modeled in this cut.
