# The beamline

*The part of LIX CORA models today, as areas you can jump to: the undulator-and-monochromator spine, the solution and scanning sample with its fluidic delivery, and the detectors, plus the controls. First cut.*

LIX (Life Science X-ray scattering) is the NSLS-II life-science scattering beamline at sector 16-ID. It resolves the structure of biological macromolecules in solution by small- and wide-angle X-ray scattering (bio-SAXS / WAXS), including in-line size-exclusion chromatography (SEC-SAXS), and maps cells and tissue with a scanning microbeam. Its PV zones run `XF:16IDA`, the optics hutch (`lix-optics`) that carries the monochromator, the white-beam and KB mirrors, the mono slit and the photon shutter; `XF:16IDB`, the transport zone (the secondary-source aperture, the fast shutter, the upstream beam-position monitor); and `XF:16IDC`, the endstation (`lix-endstation`) where the conditioned beam meets a solution flow cell or a tissue sample and the pattern is recorded on the Pilatus detectors (`ENC-1`). 16-ID is an in-vacuum-undulator source, so there is an insertion device on the spine, unlike the bending-magnet CMS (`SRC-1`).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers, conditions, focuses, and energy-selects the incident beam, the [Sample](sample.md) that places the specimen, by flow cell or on a scanning stage, at a chosen position, and the [Detector](detector.md) that records the scattered signal. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

## Stations

- [Source](../beamline.md): the storage-ring machine state read through a loose `StorageRing` (`MACHINE-1`), the in-vacuum undulator (`SRC-1`), the double-crystal monochromator (`MONO-1`), the white-beam and KB focusing mirrors (`OPT-1`), the mono slit and secondary-source aperture (`OPT-2`), the photon and fast shutters (`PSS-1`, `TRIG-1`), and in the endstation zone the compound refractive lens transfocator (`CRL-1`) and the guard slit (`OPT-2`). The incident energy is a pseudo-axis over the DCM Bragg angle and the undulator gap (`MONO-1`).
- [Sample](sample.md): the solution positioning stack (a `Manipulator`, `SAMPLE-1`) that places the flow cell; the scanning-microbeam goniometer (a `Goniometer`, `SCAN-1`) for cells and tissue; and the HPLC delivery pump (a loose `FlowController`, `FLUID-1`) that flows the solution and SEC peak through the cell. The selector valves, the SEC column, the flow cell, the sample robot, and the solution Subject are the fluidic-delivery seam and the Subject / Supply / Procedure shape (`FLUID-1`, `SEC-1`, `ROBOT-1`, `SUBJECT-1`).
- [Detector](detector.md): the SAXS and WAXS Pilatus area detectors (`DET-1`), the scanning-mode fluorescence spectrometer (`DET-1`), the detector translations (`DET-1`), the SAXS beamstop (`DET-1`), and the endstation flux and beam-position monitors (`DET-1`, `DIAG-1`). The Zebra triggers the detectors (`TRIG-1`).

## Shared

- [Controls](controls.md): the NSLS-II EPICS / ophyd control stack, the heterogeneous fluidic control plane (a Moxa terminal server, the Agilent OpenLAB .NET SDK, a pcaspy soft-IOC), and the bluesky-plan orchestration CORA's edge replaces. The device handles are bound from the beamline's profile collection and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, and vacuum for the optics and SAXS flight path), plus the bio-SAXS consumables (buffers, the SEC column, needle wash) as Supply; carried in the descriptor (`SUP-1`, `SEC-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations), including the loose families and the FlowController held at n=3.
