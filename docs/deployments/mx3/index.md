# MX3

*Macromolecular crystallography at the Australian Synchrotron: rotation MX on an MD3 microdiffractometer reading a DECTRIS Eiger, with an ISARA robot for unattended sample exchange. This page describes how CORA would model and run MX3; the model is reverse-engineered from public configuration, not yet confirmed by Australian Synchrotron staff.*

| Property | Value |
| --- | --- |
| Asset | `MX3` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [Australian Synchrotron](../as/index.md) (bound via `facility_code = "as"`, `FacilityKind = Site`) |
| Sector | PV namespace `MX3*` (storage ring at `SR11*`) |
| Institution | ANSTO, Australian Nuclear Science and Technology Organisation (context; not modeled as an Asset) |
| Status | Reverse-engineered from public config (design-phase scaffold) |
| Source | insertion device (understood to be an undulator, unconfirmed; PV not in the public library, SRC-1) |

!!! note "How CORA would land on MX3"
    These pages describe how CORA would model, govern, and conduct MX3, the first beamline of CORA's sixth Site, the [Australian Synchrotron](../as/index.md). They are not a survey of the beamline's current software. The hardware facts (devices, EPICS PVs, control interfaces) are read from public open source (the [`AustralianSynchrotron/mx3-beamline-library`](https://github.com/AustralianSynchrotron/mx3-beamline-library) device library) and verified against it; vendor part numbers and physical positions are not in it, so they, and every read value, are carried `confirm` until staff verify them ([Open questions](questions.md)). This is a design-phase scaffold: the descriptor and these docs, with scenarios deferred.

## The defining shape: a new Site, a heterogeneous control plane

MX3 brings CORA to a **sixth Site** (the first Australian facility) and, with it, a control plane unlike any prior deployment's. Most MX3 devices are EPICS-PV-bound (the storage ring at `SR11*`, the beamline at `MX3*`, with literal in-code PVs), but three first-class subsystems sit on their own control planes:

- the **MD3 microdiffractometer** goniometer over the **MXCuBE Exporter** protocol (TCP),
- the **DECTRIS Eiger** over the **SIMPLON REST** API (HTTP), the first non-EPICS area detector in the fleet,
- the **ISARA robot** over a **TCP client** library.

The value to CORA is twofold: it re-tests that the Site / Federation kernel ports to a new facility (as SLAC did), and it stresses the seam, CORA's `ControlPort` must span EPICS, Exporter, and REST at once. The *technique*, rotation MX, is not new (Diamond [I03](../i03/index.md) brought it), so MX3 introduces no new catalog Family and reuses i03's Goniometer and MX Methods.

## The beamline

Along the beam, in order:

- [Source](beamline.md): the storage-ring current monitor and the front-end shutter (the undulator source PV is not in the library, SRC-1), then the optics, the double-multilayer monochromator, the master energy axis, and the attenuator.
- [Sample](equipment/sample.md): the MD3 microdiffractometer goniometer, the cryojet cooling, the backlight, and the beamstop, plus the ISARA sample-exchange robot.
- [Detector](equipment/detector.md): the DECTRIS Eiger (over SIMPLON REST), its translation stage, the on-axis viewing camera, the flux monitor, and the beam-position / steering monitor.

Cutting across all three:

- [Controls](equipment/controls.md): the shutters, the motion controllers, and the heterogeneous control-plane seam.

The cross-cutting reference view is the [Inventory](inventory.md).

## Techniques

[Techniques](techniques.md): the rotation-MX techniques MX3 runs (data collection, grid scan, autonomous sample exchange), each reusing a pending Diamond i03 Method.

## Governance

[Governance](governance.md): who may act at MX3 and the trust shape CORA applies; CORA brings its own per-Actor authority.

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's MX3 content lives.
