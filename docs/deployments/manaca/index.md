# MANACA

*Sirius's macromolecular-crystallography beamline, and CORA's first MX beamline at Sirius (after the MOGNO tomography scaffold). This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `MANACA` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [Sirius (LNLS)](../sirius/index.md) (bound via `facility_code = "sirius"`, `FacilityKind = Site`) |
| Sector | `MANACA` (the LNLS beamline name; not a registered Asset) |
| Status | First cut, reverse-engineered, operating beamline (the optics + the MX experiment endstation; scenarios deferred) |
| Source | An undulator delivering 5-20 keV for macromolecular crystallography |
| Control stack | Sirius EPICS device floor + MXCuBE3 for the MX experiment (Bluesky / sophys named as a facility direction, ORCH-1); no public per-beamline handles, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from Sirius's public facility pages ([lnls.cnpem.br/facilities/manaca](https://lnls.cnpem.br/facilities/manaca/)) and a verified research brief. LNLS publishes its control software openly, but no per-beamline EPICS PV manifest, so the control handles are not bound; vendor part numbers, the detector model, energy details, and physical positions are open questions. Every value is carried as `confirm` until MANACA staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes MANACA different

MANACA is **Sirius's first macromolecular-crystallography beamline** and CORA's second modelled Sirius beamline, after the [MOGNO](../mogno/index.md) tomography scaffold. Sirius (the Brazilian Synchrotron Light Laboratory, Campinas) is already a modelled Site; MANACA adds MX to it. Its science is macromolecular crystallography: rotation MX on a goniometer reading an area detector, with an automated 48-pin sample changer, supporting serial and room-temperature MX at 5-20 keV. The control plane is the Sirius EPICS device floor with MXCuBE3 / MXCuBE Web as the MX experiment UI (Bluesky / Ophyd, the LNLS sophys family, is named as a facility orchestration direction, as MOGNO records, but its MANACA status is not public, `ORCH-1`).

For the modelling, MANACA is a **reuse-and-reinforce** deployment: it adds a beamline to an existing Site and coins **no new vocabulary**. It is an MX beamline, so it reuses the macromolecular-crystallography vocabulary the fleet already carries (graduated at Diamond i03, exercised at NSLS-II FMX / AMX and the Australian Synchrotron MX3):

- The MX device tree (`Goniometer`, `Camera`, `Monochromator`, `TemperatureController`, `Filter`, `BeamStop`, `Shutter`, `FluxMonitor`) reuses the established MX Families.
- The rotation-MX techniques bind the pending i03 Methods (`mx_data_collection`, `grid_scan`, `sample_exchange`), recorded as Practices on the Sirius Site.
- The 48-pin sample changer is modelled as a deferred Procedure (sample exchange), not a device family (the i03 / i24 / MX3 ROBOT-1 precedent).

MANACA coins no new Family and changes nothing in the catalog.

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics (`manaca-optics`) | Yes | The storage-ring state, the front-end shutter, the monochromator, the energy axis, the attenuators |
| MX experiment endstation (`manaca-experiment`) | Yes | The goniometer, the cryostream, the backlight, the beamstop, the area detector + its stage, the on-axis camera, the flux monitor |
| The 48-pin sample changer | Named, not built | Modelled as a deferred sample-exchange Procedure, not a device family (`ROBOT-1`) |
| The detector model | Named, not bound | The area-detector model is not published; a `Camera` Asset is carried pending (`DET-1`) |
| EPICS / MXCuBE handles | No | No public per-beamline PV manifest, carried pending, not invented (`CTRL-1`) |
| PSS permit signals and vacuum extent | No | Not published per beamline, carried pending, not invented (`PSS-1`, `SUP-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A second beamline at an existing Site.** Sirius is already modelled (`deployments/sirius/site.yaml`, the MOGNO scaffold); MANACA adds its first MX beamline. The EPICS floor + MXCuBE3 control plane is modelled with handles omitted pending, the way the MX3 and FAXTOR reverse-engineered scaffolds do (`CTRL-1`).
- **No new families.** The goniometer binds the graduated `Goniometer`, the detector `Camera`, the monochromator `Monochromator`; the catalog is unchanged (the i03 / FMX / AMX / MX3 MX precedent).
- **The sample changer is a Procedure, not a device.** The automated 48-pin changer is modelled as a deferred sample-exchange Procedure, following the established MX robot precedent (`ROBOT-1`).
- **The detector is named, not bound.** The area-detector model is unpublished; it is carried as a pending `Camera` Asset so the [Detector](equipment/detector.md) page is real (`DET-1`).

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the storage-ring state, the front-end shutter, the monochromator, the energy axis, and the attenuators.
- [Sample](equipment/sample.md): the goniometer, the cryostream, the backlight, and the beamstop.
- [Detector](equipment/detector.md): the area detector and its stage, the on-axis viewing camera, and the flux monitor.

Cutting across them:

- [Controls](equipment/controls.md): the Sirius EPICS floor + MXCuBE3 control stack and the orchestration seam; handles not published per beamline, carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/manaca/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of MANACA is designed to do, as intent. Rotation MX, grid scan, and sample exchange reuse the pending i03 Methods, carried pending (`TECH-1`, `ROBOT-1`).

## Governance

[Governance](governance.md): who will act at MANACA and the trust shape that gates their commands. People and agents are facility principals at the [Sirius Site](../sirius/index.md).

## Model

[Model](model.md): the developer's by-kind index, MANACA's place as Sirius's first MX beamline, and the record of what is deliberately deferred.

## Not yet documented

MANACA is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals and shutters are not published per beamline and are not invented here (`PSS-1`).
