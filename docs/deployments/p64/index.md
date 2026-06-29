# P64

*PETRA III's advanced X-ray absorption spectroscopy beamline, and CORA's ninth PETRA III beamline. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `P64` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PETRA III (DESY)](../petra-iii/index.md) (bound via `facility_code = "petra-iii"`, `FacilityKind = Site`) |
| Sector | `P64` (the PETRA III beamline name; not a registered Asset) |
| Status | First cut, reverse-engineered, operating beamline (the optics + experiment endstation; scenarios deferred) |
| Source | An undulator for dilute / high-rate fluorescence EXAFS / XANES |
| Control stack | PETRA III Tango device floor + Sardana scan layer; per-beamline device handles read from the public OnlineXML registry, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from P64's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p64](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p64), branch `debian/jessie`) and a verified research brief. The registry carries real Tango device names and control handles, but no crystal cuts, the detector element count, energy calibration, or physical positions; those are open questions. The experiment motor bank is grouped (per-axis roles not labelled). Every value is carried as `confirm` until P64 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes P64 different

P64 "Advanced X-ray Absorption Spectroscopy" is **CORA's ninth PETRA III beamline** and the fleet's high-rate fluorescence EXAFS beamline. It is scaffolded together with its applied-XAS sibling [P65](../p65/index.md) as the PETRA III XAS pair; the two share the optics host. Its defining feature is the **large multi-element fluorescence detector** (a 104-channel SIS3302 digitizer) for dilute, high-rate absorption spectroscopy, plus two Lambda 750k area detectors and a Tsai-geometry monochromator whose energy axis couples the undulator.

P64 coins **no new Family**: the undulator binds `InsertionDevice`, the mono `Monochromator`, the mirrors `Mirror`, the slits `Slit`, the stages `LinearStage`, the Lambda detectors `Camera`, and the multi-element fluorescence detector `EnergyDispersiveSpectrometer`. The technique (XAS) reuses the pending `xas_spectroscopy` slug the BMM / ISS / i20-1 / P04 beamlines already share (`TECH-1`).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics hutch (`p64-oh`) | Yes | The undulator, the Tsai DCM + coupled energy, the two mirrors, the slits |
| Experiment endstation (`p64-eh`) | Yes | The sample bank, the DAC sub-stage, the NewFocus picomotors, the detectors |
| The multi-element fluorescence detector | Grouped | The 104-channel SIS3302 ROI explosion is grouped as one `EnergyDispersiveSpectrometer` (`DET-1`) |
| The per-axis roles of the sample bank | Grouped, not resolved | `exp_mot` / `dac_*` not labelled per axis; grouped (`GROUP-1`) |
| Tango / Sardana handles | Yes, from the registry | Read from the public OnlineXML (`CTRL-1`) |
| PSS permit signals | No | Not in the OnlineXML; carried pending, not invented (`PSS-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A ninth beamline at an existing Site, scaffolded as the XAS pair.** P64 (advanced) and [P65](../p65/index.md) (applied) are the two PETRA III XAS beamlines, sharing the `hasnp64` optics host; both reuse the `xas_spectroscopy` Method.
- **No new Family.** Every device binds an existing catalog Family.
- **The multi-element detector is one Asset.** The 104-channel SIS3302 is grouped into a single `EnergyDispersiveSpectrometer` rather than 104 Assets, since the channels are facets of one multi-element detector (`DET-1`).
- **The mirrors are resolved.** Unlike most PETRA III banks, P64's OH mirror axes are labelled (`Mirror1*`, `Mirror2*`), so the two mirrors are modelled as resolved `Mirror` Assets.

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the undulator, the Tsai DCM, the mirror pair, the slits.
- [Sample](equipment/sample.md): the sample bank, the DAC sub-stage, the picomotors.
- [Detector](equipment/detector.md): the two Lambda 750k detectors and the multi-element fluorescence detector.

Cutting across them:

- [Controls](equipment/controls.md): the PETRA III Tango floor + Sardana scan layer and the orchestration seam; handles read from the OnlineXML, carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p64/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of P64 is designed to do, as intent. XAS reuses the pending `xas_spectroscopy` Method (`TECH-1`).

## Governance

[Governance](governance.md): who will act at P64 and the trust shape that gates their commands. People and agents are facility principals at the [PETRA III Site](../petra-iii/index.md).

## Model

[Model](model.md): the developer's by-kind index, P64's place as the advanced half of the PETRA III XAS pair, and the record of what is deliberately deferred.

## Not yet documented

P64 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals are not in the OnlineXML and are not invented here (`PSS-1`).
