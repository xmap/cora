# Controls

*The control stack and the MX-orchestration seam. First cut; no public per-beamline handles, carried confirm.*

MANACA runs on the Sirius control stack: EPICS at the device-IO floor, with MXCuBE3 / MXCuBE Web as the MX experiment UI. Sirius has named Bluesky / Ophyd (the LNLS "sophys" family) as a facility orchestration direction, and its [MOGNO](../../mogno/index.md) sibling records the same migration question (`ORCH-1`); whether MANACA runs Bluesky today is not public. CORA observes the EPICS floor and, where it replaces or drives through the MX scan orchestration, conducts over it; it does not own the EPICS layer.

## Device handles

Sirius's control software is public (the LNLS Bluesky-based "sophys" family on GitHub), but no per-beamline EPICS PV manifest is published for MANACA, so unlike a dodal or bluesky-profile config there is no public source of the beamline's real addresses. The control handles are therefore not bound; the descriptor carries the device tree with handles pending (`CTRL-1`). The stack shapes the handle forms:

| Handle form | What it addresses | Where it would appear |
| --- | --- | --- |
| EPICS PV | the device-IO floor (motors, shutters, monochromator, flux) | the optics and endstation devices |
| MXCuBE handle | the MX experiment orchestration | the goniometer, detector, and sample-changer loop |
| Ophyd device / Bluesky plan | the facility orchestration direction, if migrated (`ORCH-1`) | the scan-level device handles |

CORA would model each as an opaque control handle set at the edge, the way the MX3 and FAXTOR reverse-engineered scaffolds do: the transport (EPICS, MXCuBE, Ophyd) is a `ControlPort` adapter concern, not a difference in the Asset. The handles remain confirm-pending until LNLS staff supply them (`CTRL-1`). The full source / optics walk and the per-device list live on the generated [Source](../beamline.md) page; this page covers the control seam.

## The orchestration seam

The MANACA acquisition (the energy selection over the undulator and monochromator, the rotation-MX oscillation, the detector triggering, the automated 48-pin sample-changer load / centre / collect / unmount loop) runs through MXCuBE3 and the beamline orchestration layer. That orchestration is the seam CORA's edge replaces or drives through: CORA conducts the run over the `ControlPort`, driving the EPICS floor rather than owning it, and may either replace the orchestration or drive through it as an actuation port. The detector file-writing to the Sirius data store is the existing data-acquisition path; CORA keeps its own data-of-record (the PG event store), so it is a source to subsume, not a system CORA depends on (see [Model](../model.md)).

## Equipment protection

The Sirius personnel-safety permit signals, the front-end and photon shutters, and any equipment-protection interlock tier are not published per beamline and are not invented here (`PSS-1`). MANACA also carries hazard classes governed at the Site, not modelled here: a cryostream and its liquid-nitrogen supply, and an automated sample changer moving in the experiment hutch. The Enclosure permit shape and the hazard tier are carried pending at the Sirius Site; the governance and safety envelope follow the 2-BM shape (see [Governance](../governance.md) and [the safety envelope](../../sirius/index.md#safety-and-governance)).
