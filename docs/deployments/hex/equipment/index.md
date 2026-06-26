# The beamline

*The part of HEX CORA models today, as areas you can jump to: the source and monochromator spine, the heavy-sample endstation, and the detectors, plus the controls. First cut.*

HEX (High Energy Engineering X-ray Scattering) is the NSLS-II high-energy engineering and energy-storage beamline at sector 27-ID. It resolves microstructure and atomic structure under working conditions by high-energy X-ray imaging and tomography, energy-dispersive diffraction (EDXD), and angle-dispersive / powder diffraction (ADXD). Its source is a superconducting wiggler delivering a white beam of 30 to 250 keV and a monochromatic beam of 30 to 200 keV (`SCW-1`, `MONO-2`). The First Optics Enclosure (`hex-foe`) carries the wiggler, the low-energy filters, and the bent-Laue monochromator; the operational endstation (`hex-endstation`, the F-hutch) sits in a satellite building adjacent to Bldg. 742, about 100 m from the source, and holds the sample tower and the detectors (`ENC-1`, `SAT-1`, `LAYOUT-1`).

Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers, hardens, and energy-selects the incident beam, the [Sample](sample.md) that places the specimen at a chosen position and angle, and the [Detector](detector.md) that records the imaging, energy-dispersive, and angle-dispersive signals. Cutting across them are the [Controls](controls.md). The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to it sideways, by `controller_id`.

## Stations

- [Source](../beamline.md): the machine state read through a loose `StorageRing` (`MACHINE-1`); the superconducting wiggler (`SCW-1`); the FOE low-energy filters that harden the white beam (`FILT-1`); the bent-Laue monochromator, whose first crystal moves in for the monochromatic beam and out for white (`MONO-1`, `MONO-2`); the incident-energy pseudo-axis over it; and the front-end defining slits (`BRANCH-1`).
- [Sample](sample.md): the reconfigurable sample tower (up to 500 kg, fully removable, configs A to D, `STAGE-1`), the tomographic rotation, and the sample translations. The endstation is capable of housing user-brought in-situ environments, none modelled in this cut (`INSITU-1`).
- [Detector](detector.md): the Kinetix sCMOS imaging cameras and their scintillator-lens table, the Phantom Veo high-speed camera, the PerkinElmer flat panel for angle-dispersive diffraction (`DET-1`), the GeRM germanium strip detector for energy-dispersive diffraction (`DET-2`), and the detector / optics positioning that switches technique in the one endstation (`TECH-1`).

## Shared

- [Controls](controls.md): the NSLS-II EPICS / ophyd control stack, the same floor as the NSLS-II siblings, and the bluesky-plan orchestration CORA's edge replaces. The endstation detector handles are bound from the beamline's profile collection and carried confirm; the FOE-optics handles are pending (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (the photon beam, cooling water, and vacuum for the FOE optics); the cryogen-free wiggler draws no liquid helium (`SUP-1`).

## Reference

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families and pending confirmations), including the one loose family.
