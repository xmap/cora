# P01

*PETRA III's nuclear-resonant-scattering and inelastic / resonant-inelastic-scattering beamline, and CORA's first PETRA III beamline. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `P01` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PETRA III (DESY)](../petra-iii/index.md) (bound via `facility_code = "petra-iii"`, `FacilityKind = Site`) |
| Sector | `P01` (the PETRA III beamline name; not a registered Asset) |
| Status | First cut, reverse-engineered, operating beamline (the optics + the three experiment hutches; scenarios deferred) |
| Source | An undulator delivering 2.5-80 keV for nuclear resonant scattering and IXS / RIXS |
| Control stack | PETRA III Tango device floor + Sardana scan layer; per-beamline device handles read from the public OnlineXML registry, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from P01's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p01](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p01), branch `debian/jessie`) and a verified research brief. The registry carries real Tango device names and control handles, but no vendor part numbers, crystal cuts, energy ranges, or physical positions; those are open questions. Asset grouping (collapsing the registry's per-axis device list into the monochromator, the mirror, the sample stage) is the human curation step over the machine extraction. Every value is carried as `confirm` until P01 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes P01 different

P01 "Dynamics" is **CORA's first PETRA III beamline** and a further **Tango / Sardana control floor** (after MAX IV and ALBA). Its science is hard X-ray dynamics: nuclear resonant scattering (NRS) and nuclear inelastic scattering at Moessbauer-isotope energies in EH1, hard X-ray diffraction in EH2, and resonant inelastic X-ray scattering (RIXS) on a KB-focused spectrometer in EH3, across 2.5-80 keV. The defining instrument is the **stack of four high-resolution monochromators** in EH1 that carve the meV bandwidth the NRS energy spectrum is scanned over.

For the modelling, P01 introduces two genuinely new things and reuses everything else:

- **The control plane (`CTRL-1`).** PETRA III runs Tango with Sardana as the scan / motion SCADA layer, not EPICS. The seam model that reads "EPICS is the floor" generalizes to "Tango / Sardana is the floor", the same shape as MAX IV and a sibling of the ESRF BLISS / Tango floor. This is the first deployment whose device handles were read from a DESY OnlineXML registry.
- **The technique (`TECH-1`).** Nuclear resonant scattering and RIXS earn no catalog Method today; they are carried as pending Practices on the [PETRA III Site](../petra-iii/index.md), reusing the `inelastic_x_ray_scattering` and `resonant_inelastic_scattering` slugs ESRF ID28 / ID32 and NSLS-II IXS / SIX already share.

P01 coins **no new Family**: the monochromators bind `Monochromator`, the mirrors `Mirror`, the slits `Slit`, the lens `Transfocator`, the stages `LinearStage` / `RotaryStage` / `Table`, the sample-orientation circle `Goniometer`, the flux monitors `FluxMonitor`. The catalog is unchanged.

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics hutch 1 (`p01-oh1`) | Yes | The undulator source, the double-crystal monochromator, the two deflection mirrors, the front-end slits |
| Optics hutch 2 (`p01-oh2`) | Yes | The secondary slit, the diamond monitor, the RIXS pre-optic |
| EH1 nuclear resonant scattering (`p01-eh1`) | Yes | The four high-resolution monochromators, the CRL, the beam-defining slit, the BPM / ion chamber, the table |
| EH2 diffraction (`p01-eh2`) | Yes | The goniometer, the sample stage, the slits, the detector stage |
| EH3 RIXS (`p01-eh3`) | Yes | The KB mirror pair, the sample stage, the detector stages |
| The detector devices | Named, not bound | The OnlineXML carries detector positioning stages, not the detector devices (APD / area detector); carried pending (`DET-1`) |
| Tango / Sardana handles | Yes, from the registry | Read from the public OnlineXML; the registry branch age means some may lag the live floor (`CTRL-1`) |
| PSS permit signals | No | Not in the OnlineXML (which carries beamline devices, not interlock leaves), carried pending, not invented (`PSS-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A new Site and its first beamline.** PETRA III is a new Site (`deployments/petra-iii/site.yaml`); P01 is its first beamline. The Tango / Sardana control plane is modelled with the handles read from the OnlineXML, the way the ESRF BLISS scaffolds read the BLISS Beacon config (`CTRL-1`).
- **No new families.** Every device binds an existing catalog Family; the catalog is unchanged (the ID19 Tango precedent: hold the device families constant, move the control axis).
- **The EH2 sample circle is a Goniometer, not a Diffractometer.** The registry exposes only theta / two-theta. That is modelled as a `Goniometer` Asset (the sample-orientation circle), not the composed `Diffractometer` Assembly, until the full circle count and a detector arm are confirmed (`DIFF-1`).
- **The detectors are named, not bound.** The OnlineXML lists detector positioning stages but not the detector devices; they are carried pending so the [Detector](equipment/detector.md) page is real (`DET-1`).

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the undulator, the two optics hutches, and the three experiment hutches.
- [Sample](equipment/sample.md): the high-resolution monochromator stack and CRL in EH1, the goniometer and sample stage in EH2, the KB pair and sample stage in EH3.
- [Detector](equipment/detector.md): the detector positioning stages in EH2 and EH3; the detector devices themselves carried pending.

Cutting across them:

- [Controls](equipment/controls.md): the PETRA III Tango floor + Sardana scan layer and the orchestration seam; handles read from the OnlineXML, carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p01/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of P01 is designed to do, as intent. Nuclear resonant scattering and RIXS earn no catalog Method today and are carried pending, reusing the IXS / RIXS slugs the fleet already shares (`TECH-1`).

## Governance

[Governance](governance.md): who will act at P01 and the trust shape that gates their commands. People and agents are facility principals at the [PETRA III Site](../petra-iii/index.md).

## Model

[Model](model.md): the developer's by-kind index, P01's place as CORA's first PETRA III beamline and a further Tango / Sardana floor, and the record of what is deliberately deferred.

## Not yet documented

P01 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals and shutters are not in the OnlineXML and are not invented here (`PSS-1`).
