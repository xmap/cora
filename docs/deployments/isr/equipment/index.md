# The beamline

*The part of ISR CORA models today, as areas you can jump to: the optics spine, the partial sample endstation, and the detectors, plus the controls. A deliberately partial first cut.*

ISR (In Situ and Resonant hard X-ray studies) is the NSLS-II 4-ID beamline for resonant scattering near absorption edges, surface and interface diffraction (crystal truncation rods), and in-situ sample environments. Its PV zones run `FE:C04A` (the front-end slit), `XF:04IDA-OP` / `XF:04IDB-OP` (the optics: the DCM, the focusing pair, the harmonic-rejection mirror), `XF:04IDA/B/C-BI` (diagnostics: screen cameras, the beam-position monitor), and `XF:04IDD-ES` (the zone-D endstation: the filter bank, the two bound sample axes, the Eiger) (`ENC-1`). 4-ID is an in-vacuum-undulator source (read-only gap in source) (`SRC-1`).

This is a partial cut, because the public source is an early, optics-first profile collection: the [Sample](sample.md) station has only two bound axes and the multi-circle diffractometer that ISR's science needs is absent (`DIFF-1`). Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that conditions and energy-selects the beam, the [Sample](sample.md) that (partially) orients the specimen, and the [Detector](detector.md) that records the scattered signal. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

## Stations

- [Source](../beamline.md): the storage-ring machine state read through a loose `StorageRing` (`MACHINE-1`), the in-vacuum undulator gap (`SRC-1`), the double-crystal monochromator (`MONO-1`), the bendable focusing pair and the harmonic-rejection mirror (`OPT-1`), the front-end slit (`OPT-2`), and the four-foil attenuator bank (`ATTN-1`). A wired resonant energy axis is absent in source (`RESONANT-1`).
- [Sample](sample.md): the two bound endstation axes (`th` / `zeta`) of the `Dif:ISD` diffractometer, modelled as one `RotaryStage` (`DIFF-1`). The full multi-circle diffractometer and the in-situ sample environment are absent from source (`DIFF-1`, `INSITU-1`).
- [Detector](detector.md): the Eiger 1M area detector (the primary scattering detector, `DET-1`), the diagnostic YAG-screen cameras (`DIAG-1`), and the motorized beam-position monitor (`DIAG-1`). The flux-monitor electrometers are commented out in source (`DET-1`).

## Shared

- [Controls](controls.md): the NSLS-II EPICS / ophyd control stack, the bluesky-queueserver + Tiled data plane, and the early-commissioning signals (commented-out devices, a stubbed energy axis, a placeholder catalog name). The device handles are bound from the beamline's profile collection and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, and vacuum for the optics); carried in the descriptor (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations), plus the list of mission devices deliberately absent from this cut.
