# Controls

*The control stack and the Sardana-orchestration seam. First cut; no public per-beamline handles, carried confirm.*

FAXTOR runs on the ALBA Tango / Sardana / Taurus control stack, the fleet's second Tango / Sardana controls house-style after MAX IV (the rest are EPICS, and the ESRF is BLISS). ALBA is the originating institution of Sardana, so this is the house-style's home facility. CORA observes that floor and, where it replaces Sardana-style scan orchestration, conducts over it; it does not replace Sardana.

## Device handles

ALBA publishes no per-beamline device manifest (the `sardana-alba` repo carries generic, shared controller plugins, not a `bl31-*` configuration), so unlike the ESRF BLISS Beacon database there is no public source of FAXTOR's real addresses. The control handles are therefore not bound; the descriptor carries the device tree with handles pending (`CTRL-1`). The transport shapes the handle forms the stack uses:

| Handle form | What it addresses | Where it would appear |
| --- | --- | --- |
| Tango device URL | motor and detector device servers | the rotary, positioning, shutter, and camera |
| IcePAP host + address | the motor-controller crates | the endstation motion axes |
| Sardana Pool / axis name | the controllers, motors, and measurement groups | the scan-level device handles |

CORA would model each as an opaque control handle set at the edge, the way the MX3 and ID32 heterogeneous-control precedents do: the transport (Tango, IcePAP, Sardana) is a `ControlPort` adapter concern, not a difference in the Asset. The handles remain confirm-pending until ALBA staff supply them (`CTRL-1`). The full source / optics walk and the per-device list live on the generated [Source](../beamline.md) page; this page covers the control seam.

## The orchestration seam

The FAXTOR acquisition (the energy selection over the wiggler and the monochromator or filters, the continuous-rotation tomography trajectory, the camera triggering off the rotary master clock, the flat / dark sequencing) runs through Sardana scan macros over a Pool and a MacroServer. That orchestration is the seam CORA's edge replaces: CORA conducts the run over the `ControlPort`, driving through Tango / IcePAP rather than replacing Sardana. The live Sardana controllers that compute the trajectories and the measurement groups stay the floor; CORA names the rotation, energy, and detector axes and records the moves, the controller owns the kinematics (`TRIG-1`). The Lima detector file-writing to the ALBA data store is plumbing CORA observes, not data it owns; CORA keeps its own data-of-record (see [Model](../model.md)).

## Equipment protection

The ALBA personnel-safety permit signals, the front-end and photon shutters, and any equipment-protection interlock tier are not published per beamline and are not invented here (`PSS-1`). The Enclosure permit shape and the hazard tier are carried pending at the ALBA Site; the governance and safety envelope follow the 2-BM shape (see [Governance](../governance.md) and [the safety envelope](../../alba/index.md#safety-and-governance)).
