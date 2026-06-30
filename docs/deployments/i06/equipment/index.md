# The beamline

*The part of i06 CORA models today, as areas you can jump to: a shared soft X-ray spine and its two endstations, the sample and detector sides of each, plus the controls and the resources they draw on. Reverse-engineered scaffold.*

i06 is the Diamond Light Source nanoscience soft X-ray beamline at Sector 06, and it is shaped differently from the single-line deployments around it. One spine, the plane-grating monochromator fed by a twin APPLE-II undulator source, conditions and energy-selects the beam and then splits it to **two endstations**: i06-1 for diffraction and dichroism, and i06-2 for photoemission electron microscopy (PEEM). The whole spine, the source, and the two stations form one CORA Asset tree under the root Unit `I06`.

i06 is also a beamline of firsts for CORA. It is the first whose source is an APPLE-II undulator, so it is the first that drives the X-ray **polarization** as an experiment axis alongside the incident-energy axis, which is what magnetic dichroism needs. And i06-2 is CORA's first PEEM endstation, an electron-imaging technique distinct from the electron-energy analysis of ARPES.

Three access-gated enclosures contain it: a shared i06-optics zone (`BL06I`), the i06-1 diffraction-dichroism endstation (`BL06J`), and the i06-2 PEEM endstation (`BL06K`) (ENC-1). The PV zones follow that split: `BL06I` carries the optics spine (the PGM, the APPLE-II controllers, the i06-branch PEEM stage), `SR06I` carries the APPLE-II servo crates (`SERVC-01` / `SERVC-21`), `BL06J` carries i06-1, and `BL06K` carries i06-2.

Along and across the beam sit two kinds of thing. In beam order are the **stations**: the [Source](../beamline.md) that delivers, conditions, energy-selects, and now polarizes the beam, the [Sample](sample.md) side of each endstation, and the [Detector](detector.md) side of each. Cutting across them are the [Controls](controls.md) and the resources the beamline draws on. The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to that apparatus sideways, by `controller_id`, and a resource is a Supply in its own right.

## Stations

- [Source](../beamline.md): the shared optics spine. The storage ring as observed machine state, the twin APPLE-II undulators (the downstream IDD and the upstream IDU), the soft X-ray plane-grating monochromator, and the two driven beam axes: the incident-energy pseudo-axis (70-2200 eV) over the PGM and the APPLE-II gap (MONO-1), and the fleet-first polarization pseudo-axis over the APPLE-II phase rows, with the value domain LH / LV / PC / NC / LA plus third-harmonic variants (POL-1, POL-2). The [source walk](../beamline.md) is the generated page; it traces each device.
- [Sample](sample.md): the sample side of both endstations. For i06-1, the diffractometer (sample circles plus the detector arm), the XAS / absorption stage carried as a design-phase placeholder (STAGE-1), and the two Lakeshore 336 temperature controllers (TEMP-1). For i06-2, the UHV PEEM sample manipulators (MANIP-1).
- [Detector](detector.md): the detector side of both endstations. For i06-1, the reciprocal-space axis over the diffractometer circles (DIFF-2) and the detector arm. The i06-1 diffraction scattering detector and any incident-flux or drain-current (electron-yield) monitor are absent from dodal and are deferred, not invented (DET-1). For i06-2, the PEEM electron-optical column and its magnified electron-image detector are likewise absent from dodal and deferred (PEEM-1).

## Shared

- [Controls](controls.md): the Diamond EPICS / ophyd-async control stack, the same floor as I22, I03, I15-1, I11, and I24, with the real dodal PV handles carried confirm (CTRL-1). CORA observes the floor and, where it replaces bluesky-style orchestration, conducts over it; it does not replace EPICS.
- Resources: the continuously-available supplies a run needs (photon beam, cooling water, and UHV vacuum for the optics path and the endstation chambers); carried in the descriptor, with no operations page in this scaffold (SUP-1).

## Reference

The cross-cutting view that spans every area:

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families, the dodal control handles, and pending confirmations). i06 earns no new Family: the APPLE-II reuses `InsertionDevice` (the same source-undulator anatomy as the EPUs at SIX, CSX, and ESM), polarization reuses `PseudoAxis` as a sibling of the incident-energy axis, and the PEEM manipulators reuse `Manipulator`. The PSS search-and-secure permit signals and the photon and front-end shutters are absent from dodal and carried pending, not invented (PSS-1).
