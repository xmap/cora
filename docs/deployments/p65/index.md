# P65

*PETRA III's applied X-ray absorption spectroscopy beamline, and CORA's tenth PETRA III beamline. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `P65` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PETRA III (DESY)](../petra-iii/index.md) (bound via `facility_code = "petra-iii"`, `FacilityKind = Site`) |
| Sector | `P65` (the PETRA III beamline name; not a registered Asset) |
| Status | First cut, reverse-engineered, operating beamline (the optics + experiment endstation; scenarios deferred) |
| Source | An undulator for applied / high-throughput EXAFS / XANES |
| Control stack | PETRA III Tango device floor + Sardana scan layer; per-beamline device handles read from the public OnlineXML registry, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from P65's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p65](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p65), branch `debian/jessie`) and a verified research brief. The P65 registry slice is thin: an energy axis, an experiment sample bank, a slit / table, and the undulator. The XAS detection (ion chambers / fluorescence) is not exposed as a device and is carried pending. Every value is carried as `confirm` until P65 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes P65 different

P65 "Applied X-ray Absorption Spectroscopy" is **CORA's tenth PETRA III beamline** and the applied / high-throughput half of the PETRA III XAS pair, the sibling of the advanced [P64](../p64/index.md). It shares the optics host with P64. Its science is routine transmission + fluorescence EXAFS / XANES for applied materials / catalysis / battery studies.

P65 is a **reuse-and-reinforce** deployment: it coins no new vocabulary. The undulator binds `InsertionDevice`, the CDCM energy axis `Monochromator`, the stages `LinearStage`, the slit `Slit`, the table `Table`. The technique (XAS) reuses the pending `xas_spectroscopy` slug (`TECH-1`).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics (`p65-oh`, shared with P64) | Yes | The undulator, the CDCM energy axis, the optics / front-end banks |
| Experiment endstation (`p65-eh`) | Yes | The sample bank, the experiment slit, the table |
| The detection | Pending placeholder | Ion chambers / fluorescence not exposed in this registry slice (`DET-1`) |
| The per-axis roles of the banks | Grouped, not resolved | `oh_*`, `fe_*`, `a2_*` not labelled per axis; grouped (`GROUP-1`) |
| The a2 dummy stubs | Noted, not modelled | `a2_dmy*` placeholder devices (`STUB-1`) |
| Tango / Sardana handles | Yes, from the registry | Read from the public OnlineXML; optics on the shared `hasnp64` host (`HOST-1`, `CTRL-1`) |
| PSS permit signals | No | Not in the OnlineXML; carried pending, not invented (`PSS-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A tenth beamline at an existing Site, the applied half of the XAS pair.** P65 (applied) and [P64](../p64/index.md) (advanced) are the two PETRA III XAS beamlines, sharing the `hasnp64` optics host; both reuse the `xas_spectroscopy` Method.
- **A thin, honest model.** The P65 registry slice exposes little beyond the energy axis and the sample bank; the detection is carried as a pending placeholder rather than invented (`DET-1`), the same model-what-the-source-supports posture as P11 and the thinner reverse-engineered scaffolds.
- **Shared optics on the P64 host.** The CDCM energy and optics banks report on the `hasnp64` host (P64's optics); per the cross-host mapping decision they are homed in the `p65-oh` enclosure with the host flagged (`HOST-1`).

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the undulator, the CDCM energy axis, the optics banks.
- [Sample](equipment/sample.md): the experiment sample bank, the slit, the table.
- [Detector](equipment/detector.md): the XAS detection (carried pending).

Cutting across them:

- [Controls](equipment/controls.md): the PETRA III Tango floor + Sardana scan layer and the orchestration seam; handles read from the OnlineXML, carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p65/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of P65 is designed to do, as intent. XAS reuses the pending `xas_spectroscopy` Method (`TECH-1`).

## Governance

[Governance](governance.md): who will act at P65 and the trust shape that gates their commands. People and agents are facility principals at the [PETRA III Site](../petra-iii/index.md).

## Model

[Model](model.md): the developer's by-kind index, P65's place as the applied half of the PETRA III XAS pair, and the record of what is deliberately deferred.

## Not yet documented

P65 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals are not in the OnlineXML and are not invented here (`PSS-1`).
