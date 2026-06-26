# IOS

*The In situ and Operando Soft X-ray Spectroscopy beamline at NSLS-II, beamline 23-ID-2: surface and interface chemistry under working conditions by ambient-pressure X-ray photoemission (AP-XPS / AP-PES) and soft NEXAFS / XAS. IOS is the twin of [CSX](../csx/index.md), sharing the same canted 23-ID twin-EPU straight. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `IOS` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 23` (the 23-ID-2 branch; PV namespace `XF:23ID*`; not a registered Asset) |
| Status | First cut, reverse-engineered, design-phase (descriptor + docs; scenarios deferred) |
| Source | Two elliptically-polarizing undulators on the canted `SR:C23-ID` straight (shared with CSX) (`SRC-1`) |
| Control stack | NSLS-II EPICS / ophyd (the same floor as FXI / HXN / SRX / BMM / SIX / CHX / CSX / ESM / SMI); handles bound from the profile collection, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/ios-profile-collection](https://github.com/NSLS2/ios-profile-collection)). EPICS PVs are real and read from the `startup/*.py` files; vendor part numbers, serials, and physical positions are not in the profile collection and are open questions. Every value is carried as `confirm` until IOS staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes IOS different

Be honest about this beamline: most of IOS is reinforcement, not novelty. Its photoemission, its soft monochromator, its fluorescence detection, and its sample manipulator all overlap the fleet's soft X-ray beamlines:

- **Photoemission reuses `ElectronAnalyzer`.** IOS's SPECS hemispherical analyzer is the third sighting of the analyzer Family after [ESM](../esm/index.md) (ARPES) and [SST](../sst/index.md) (HAXPES), and the first non-Scienta and first ambient-pressure one. The analyzer make, the lens-mode set, and the pass-energy range are a per-Asset settings difference, not a Family split.
- **The monochromator reuses `GratingMonochromator`.** Its VLS-PGM (200-2200 eV) is a further consumer of the soft X-ray plane-grating Family after SIX / CSX / ESM / SST.
- **The fluorescence detectors reuse `EnergyDispersiveSpectrometer`.** The Vortex and the Xspress3 silicon-drift detectors bind the same energy-dispersive Family the absorption / fluorescence beamlines already use.
- **The sample stage reuses `Manipulator`.** The AP-PES four-axis stage is a further consumer after SIX / ESM / SST / I06.
- **The source is the CSX straight.** The two canted EPUs are the same `SR:C23-ID` twin-EPU straight CSX reads on the 23-ID-1 branch; IOS is the 23-ID-2 branch (`TOPO-1`).

IOS has one genuinely distinct contribution, and CORA carries it as a deferral rather than inventing it:

- **In-situ / operando ambient-pressure spectroscopy.** IOS measures chemistry under a working gas atmosphere, which is what "ambient-pressure" and "operando" mean: the reaction cell, the gas dosing and mixing, the pressure control, and the sample heating are the heart of the beamline. The profile collection exposes none of that hardware (no gas, pressure, or temperature PVs), so per "do not invent," the ambient-pressure sample environment is the headline open question (`INSITU-1`), modelled by what is real (the `Manipulator` and the analyzer), not coined as a device.

IOS coins **no new Family**, nothing graduates, and the catalog is unchanged. It also exercises the NSLS-II Site and Federation kernel once more, alongside its fleet siblings. Read the rest of these docs around what is distinct, the ambient-pressure environment carried as `INSITU-1`, and read the photoemission and absorption as the fleet shapes ported, not invented.

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics (`XF:23IDA`, `XF:23ID2-OP`) | Yes | The two canted EPUs, the front-end mirrors, the VLS-PGM, the branch mirror, the KB focusing pair, and the branch slits (`ENC-1`) |
| Endstation (`XF:23ID2-ES`, `XF:23ID2-BI`) | Yes | The AP-PES manipulator, the XAS sample stage, the SPECS analyzer, the Vortex / Xspress3 fluorescence detectors, the scaler / yield chain, the Au-mesh I0 monitor, and the surface-prep ion gun (`ENC-1`) |
| New device classes | None | Zero new Families coined; nothing graduates; the catalog is unchanged |
| The ambient-pressure reaction cell | No (not in source) | Gas dosing, pressure control, and sample heating are absent from the profile collection and not invented (`INSITU-1`) |
| Sample transfer / load-lock | No (partial in source) | A load-lock gate valve (`IOXAS-GV:4`) is present but no transfer-motor PVs are (`SAMPLE-1`) |
| Integration scenarios + vendor Models | No | Design-phase; the descriptor and docs come first |

The deferred parts are recorded on [Model](model.md).

## Key modelling decisions

- **Reuse over coin.** Every device binds an existing catalog Family, and the catalog changes nothing. No new soft X-ray abstraction is earned here.
- **The SPECS analyzer binds `ElectronAnalyzer`.** It is the third sighting after ESM and SST and the first non-Scienta / first ambient-pressure one; analyzer make and pass-energy range are a per-Asset settings difference, not a Family split (`DET-1`).
- **The ambient-pressure environment is a deferral, not a device.** There are no gas / pressure / temperature PVs in the profile collection, so IOS's defining reaction cell is the headline open question, modelled by the real `Manipulator` and analyzer, not coined (`INSITU-1`).
- **The two canted EPUs are the CSX straight.** IOS reads the 23-ID-2 branch of the same `SR:C23-ID` twin-EPU straight CSX reads on 23-ID-1; one root Unit, the 32-ID / CSX precedent (`TOPO-1`, `SRC-1`).
- **No Practice is recorded yet.** IOS's ambient-pressure photoemission and soft NEXAFS sit on pending and deferred Methods, so following [SST](../sst/techniques.md), no Practice is bound at the [NSLS-II Site](../nsls2/index.md) until a Method lands; IOS is bound via the beamline list (`TECH-1`, `ENERGY-1`).
- **Zero new Families coined, nothing graduates, the catalog is unchanged.**

## The beamline

- [Source](beamline.md): the generated device walk: the two canted EPUs, the front-end mirrors, the VLS-PGM, the branch mirror, the KB focusing pair, and the branch slits.
- [Sample](equipment/sample.md): the AP-PES four-axis manipulator, the XAS sample stage, the surface-prep ion gun, and the deferred ambient-pressure reaction cell.
- [Detector](equipment/detector.md): the SPECS hemispherical analyzer, the Vortex and Xspress3 fluorescence detectors, the scaler and electron-yield chain, and the Au-mesh I0 monitor.

Cutting across them:

- [Controls](equipment/controls.md): the EPICS / ophyd control stack and the bluesky-orchestration seam; handles bound from the profile collection and carried confirm (`CTRL-1`).

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/ios/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of IOS is designed to do, as intent. Ambient-pressure photoemission (AP-XPS) and soft NEXAFS / XAS both sit on pending or deferred Methods, so they render unlinked and IOS records no Practice yet, following SST (`TECH-1`, `ENERGY-1`).

## Governance

[Governance](governance.md): who will act at IOS and the trust shape that gates their commands. People and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here), surfacing through their actions and gated by a Zone-plus-Conduit-plus-Policy trust shape. The NSLS-II operator pool and review are pending at the Site (`GOV-1`). PSS search-and-secure permit signals and the photon shutters are absent from the profile collection and carried pending, not invented (`PSS-1`).

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's IOS content lives, and the record of what is deliberately deferred. IOS introduces no new Family.

## Not yet documented

IOS is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The ambient-pressure reaction cell, the PSS permit signals, and the shutters that are absent from the profile collection are not invented here (`INSITU-1`, `PSS-1`).
