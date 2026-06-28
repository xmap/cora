# Controls

*The control stack and trigger scheme. Modelling exercise; handles not public.*

I-TOMCAT runs on the SLS control stack: EPICS at the floor ("control of the beamline and experiment is fully implemented in EPICS"), with the BEC (Beamline and Experiment Control) microservice scan/orchestration layer over ophyd introduced for SLS 2.0. EPICS is the same floor the APS pilot uses; the BEC scan layer is the SLS-specific edge.

## The seam

CORA's lens names the facility's software only to draw the boundary:

- **EPICS (floor): drive through.** CORA actuates and observes the beamline over EPICS, never replacing it. This matches the 2-BM and FXI posture (EPICS is the floor).
- **BEC (edge): replace.** CORA's edge would replace BEC's scan and experiment steering, conducting over EPICS rather than replacing it, the way it replaces TomoScan at 2-BM. The wrinkle is that BEC adopts the same ophyd device model CORA's edge would, which keeps a drive-through reading (integrate at the `bec_messages` / ophyd boundary) open. This is the single most consequential seam decision and is carried as SEAM-1 on [Open questions](../questions.md).
- **SciCat + the reconstruction pipeline: replace / observe.** The Ra/SLURM Fiji reconstruction pipeline and the SciCat catalog are plumbing CORA observes; CORA owns its own Dataset rather than adopting SciCat as its source-of-record.

## Device handles

CORA models each device's control handle as an opaque string set at the edge, independent of the control system. For I-TOMCAT the EPICS PV prefix scheme is not public and the BEC ophyd device manifest lives on the internal gitlab.psi.ch, so every device's handle is left empty in the [descriptor](../inventory.md) rather than filled with an invented value. Wiring each Asset to a real handle is tracked by CTRL-1 on [Open questions](../questions.md).

The public ophyd device configs for sibling SLS beamlines (cSAXS `X12SA-...`, PXIII `X06DA-...`) show the PV-prefix shape CORA would mine, but no equivalent is public for TOMCAT (`X02SA`).

## Triggering

The air-bearing rotation stage is expected to be the master clock, feeding the camera trigger inputs for continuous and streaming acquisition. The exact trigger/sync hardware is not public and may differ from 2-BM's softGlueZynq box; the chain is modelled as a single `TimingController` device carrying the scheme, with the conditioner question left open (TRIG-1).
