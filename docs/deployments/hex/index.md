# HEX

*The High Energy Engineering X-ray Scattering beamline at NSLS-II, beamline 27-ID: engineering-materials and energy-storage science by high-energy X-ray imaging and tomography, energy-dispersive diffraction (EDXD), and angle-dispersive / powder diffraction (ADXD), from a superconducting wiggler. HEX is the fleet's first true high-energy hard X-ray beamline. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `HEX` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 27` (PV namespace `XF:27ID*`; not a registered Asset) |
| Status | First cut, reverse-engineered, design-phase (descriptor + docs; scenarios deferred) |
| Source | A superconducting wiggler (4.3 T, 70 mm period); white beam 30 to 250 keV, monochromatic 30 to 200 keV (`SCW-1`, `MONO-2`) |
| Control stack | NSLS-II EPICS / ophyd (the same floor as the NSLS-II siblings); handles bound from the profile collection, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    HEX is an operating beamline, but this scaffold was reverse-engineered from public sources (the BNL beamline page, the [beamline 27-ID wiki](https://wiki-nsls2.bnl.gov/beamline27ID), and the beamline's bluesky profile collection [NSLS2/hex-profile-collection](https://github.com/NSLS2/hex-profile-collection) and [NSLS2/hextools](https://github.com/NSLS2/hextools)). The endstation detector EPICS PVs are real and read from the `startup/*.py` files; the FOE-optics PVs, vendor part numbers, and physical positions are not in the profile collection and are open questions. Every value is carried as `confirm` until HEX staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes HEX different

Be honest about this beamline: much of HEX is reinforcement, not novelty. Its X-ray imaging and tomography overlap the fleet heavily, the [2-BM](../2-bm/index.md) operational pilot and the NSLS-II [FXI](../fxi/index.md) both do tomography, and its high-energy diffraction reuses the energy-dispersive and powder-diffraction shapes the fleet already debates as pending Methods (APS [7-BM](../7-bm/index.md) energy-dispersive diffraction, Diamond [i11](../i11/index.md) powder diffraction). The imaging and diffraction reuse the existing `Camera` / `Scintillator` / `RotaryStage` / `LinearStage` / `EnergyDispersiveSpectrometer` vocabulary, coin no new Family, and sit on the same pending Method slugs the siblings left deferred.

HEX has three genuinely distinct contributions:

- **Multi-technique in one experiment.** Imaging / tomography, EDXD, and ADXD are all available in the single operational endstation (the F-hutch) during the same experiment, with detectors and optics moved into place remotely per technique. This stresses the one-technique-per-acquisition assumption and the Controls seam: a technique switch is a positioning leg over the `ControlPort`, not a new Capability (`TECH-1`).
- **Very large and heavy engineering samples.** The sample tower carries up to 500 kg and is fully removable for custom in-situ / operando environments. The heavy reconfigurable fixture reuses `Table` + `RotaryStage` + `LinearStage` with capacity and configuration as settings; no `HeavyStage` Family is coined (`STAGE-1`).
- **A high-energy hard X-ray source.** The superconducting wiggler reaching 200 keV monochromatic is a first for the fleet. It binds the existing `InsertionDevice` Family (the undulator precedent), with the high field and energy reach carried as source specs (`SCW-1`).

HEX coins **no new Family**, nothing graduates, and the catalog is unchanged. Frame the rest of these docs around what is distinct, the multi-technique endstation, the heavy samples, and the high-energy source, and read the imaging and diffraction as the fleet shape ported, not invented.

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| FOE optics (`hex-foe`) | Yes | The superconducting wiggler, the low-energy filters, the bent-Laue monochromator, the incident-energy axis, and the front-end slits (`ENC-1`) |
| Endstation (`hex-endstation`, the F-hutch) | Yes | The 500 kg sample tower, the tomographic rotation and translations, the Kinetix and Phantom cameras, the PerkinElmer flat panel, the GeRM strip detector, and the technique-switch positioning (`ENC-1`, `SAT-1`) |
| The B / C / D / E hutches | Declared (device-free shells) | Forward-looking: all six designed enclosures are declared, but B (not erected) and C / D / E (future-upgrade shells) carry no devices; the operational beam path is FOE to F-hutch (`ENC-1`, `LAYOUT-1`) |
| New device classes | None | Zero new Families coined; nothing graduates; the catalog is unchanged |
| The technique switch (imaging / EDXD / ADXD) | Method + positioning leg | Multiple Methods over one endstation, with a `LinearStage` positioning the detectors and optics; no new Capability (`TECH-1`) |
| The monochromatic focusing optic | No (being commissioned) | Listed as "being commissioned" on the beamline page; not yet a device (`FOCUS-1`) |
| In-situ rigs (load frames, furnaces, cryostats, battery cyclers) | No (none confirmed installed) | The endstation is "capable of housing" user-brought environments; no specific rig is source-confirmed (`INSITU-1`) |
| Integration scenarios + vendor Models | No | Design-phase; the descriptor and docs come first |

The deferred parts are recorded on [Model](model.md).

## Key modelling decisions

- **Reuse over coin.** Every device binds an existing catalog or loose Family, and the catalog changes nothing. No second fleet beamline has yet earned a new abstraction here.
- **The superconducting wiggler binds `InsertionDevice`.** The high field (4.3 T) and the energy reach (to 200 keV monochromatic) are source specs carried on the Asset, not a new Family (`SCW-1`). The beam mode (white versus monochromatic) is selected by inserting or retracting the monochromator first crystal, so it is a setting on the optic, not a second source (`MONO-2`).
- **The GeRM strip detector binds the existing `EnergyDispersiveSpectrometer`.** The germanium energy-dispersive-diffraction detector is the third consumer of a Family already earned by the APS 2-ID fluorescence detector and the 7-BM germanium detector. It is a reuse, not a graduation (`DET-2`).
- **The 500 kg sample tower binds `Table`.** The heavy removable fixture reuses the support-table Family with load capacity and the configuration set (configs A to D) as settings; the tomographic rotation binds `RotaryStage` and the translations `LinearStage` (`STAGE-1`).
- **The multi-technique switch is a positioning leg, not a Capability.** Imaging, EDXD, and ADXD run in one endstation; moving a detector or optic into the beam binds `LinearStage` and is conducted over the `ControlPort` (`TECH-1`).
- **Zero new Families coined, nothing graduates, the catalog is unchanged.**

## The beamline

- [Source](beamline.md): the generated device walk: the storage-ring machine state, the superconducting wiggler, the low-energy filters, the bent-Laue monochromator and the beam-energy pseudo-axis over it, and the front-end slits.
- [Sample](equipment/sample.md): the reconfigurable 500 kg sample tower, the tomographic rotation, and the sample translations.
- [Detector](equipment/detector.md): the Kinetix sCMOS imaging cameras and their scintillator-lens table, the Phantom Veo high-speed camera, the PerkinElmer flat panel (ADXD), the GeRM germanium strip detector (EDXD), and the detector / optics positioning that switches technique.

Cutting across them:

- [Controls](equipment/controls.md): the EPICS / ophyd control stack and the bluesky-orchestration seam; handles bound from the profile collection and carried confirm (`CTRL-1`).

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/hex/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of HEX is designed to do, as intent. Tomography and radiography map to `tomography` (graduated, shared with 2-BM / FXI) and `radiography` (shared with 7-BM); energy-dispersive diffraction maps to `energy_dispersive_diffraction` (shared with 7-BM); angle-dispersive / powder diffraction maps to `powder_diffraction` (shared with i11). The diffraction Methods render unlinked, carried pending (`TECH-1`).

## Governance

[Governance](governance.md): who will act at HEX and the trust shape that gates their commands. People and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here), surfacing through their actions and gated by a Zone-plus-Conduit-plus-Policy trust shape. HEX adds one distinct governance fact: a share of beamtime is reserved for NYSERDA-aligned, New York clean-energy proposals, scored by a dedicated evaluation committee (`GOV-1`). PSS search-and-secure permit signals and the shutters are absent from the profile collection and carried pending, not invented (`PSS-1`).

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's HEX content lives, and the record of what is deliberately deferred. HEX introduces no new Family.

## Not yet documented

HEX is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS search-and-secure permit signals and shutters are absent from the profile collection and are not invented here (`PSS-1`).
