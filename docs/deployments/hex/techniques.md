# Techniques

*What the modelled part of HEX is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../nsls2/index.md#the-techniques-adapted-here) is how a facility adapts it. HEX measures engineering-materials and energy-storage samples three ways, all in the single operational endstation and all at high X-ray energy: X-ray imaging and tomography, energy-dispersive X-ray diffraction (EDXD), and angle-dispersive / powder diffraction (ADXD). One of those, tomography, is a Method CORA already holds; the rest render unlinked and are carried pending until the owner-scope decision (`TECH-1`) brings them into the catalog.

HEX is mostly reinforcement of imaging and high-energy diffraction the fleet already speaks. Read this page for the one thing that is structurally distinct: all three techniques run in the same experiment, with detectors and optics moved into the beam remotely.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| X-ray tomography and CT | `tomography` | high-energy white-beam and monochromatic tomography (continuous fly-rotation, `tomo_flyscan`) on the [Kinetix sCMOS cameras](equipment/detector.md); reuses the graduated Method (shared with [2-BM](../2-bm/techniques.md) and [FXI](../fxi/techniques.md)) |
| Time-resolved radiography | `radiography` | 2D high-speed / in-situ radiography on the [Phantom Veo](equipment/detector.md); shares the Method APS [7-BM](../7-bm/techniques.md) left pending (`TECH-1`) |
| Energy-dispersive diffraction (EDXD) | `energy_dispersive_diffraction` | spatially-resolved EDXD on the [GeRM germanium strip detector](equipment/detector.md); shares the Method 7-BM left pending, HEX the second consumer (`TECH-1`) |
| Angle-dispersive / powder diffraction (ADXD) | `powder_diffraction` | monochromatic area-detector diffraction on the [PerkinElmer flat panel](equipment/detector.md); shares the Method Diamond [i11](../i11/techniques.md) left pending, HEX the second consumer (`TECH-1`) |

All four techniques need the [incident-beam chain](beamline.md) (the superconducting wiggler, the low-energy filters, and the monochromator for the monochromatic modes), the [sample stack](equipment/sample.md) (the 500 kg sample tower, the tomographic rotation and translations), and the [endstation detectors](equipment/detector.md). The white beam serves high-speed imaging and EDXD; the monochromatic beam serves tomography at a chosen energy and angle-dispersive diffraction.

## The imaging and diffraction is reinforcement, not novelty

Tomography, radiography, and high-energy diffraction overlap the fleet. Tomography is the operational pilot's defining technique ([2-BM](../2-bm/techniques.md)) and is graduated in the catalog; the [FXI](../fxi/techniques.md) full-field microscope is a second tomography sibling. Energy-dispersive diffraction is the pending APS [7-BM](../7-bm/techniques.md) white-beam Method, and angle-dispersive / powder diffraction is the pending Diamond [i11](../i11/techniques.md) Method. HEX reuses the same `Camera` / `Scintillator` / `RotaryStage` / `LinearStage` / `EnergyDispersiveSpectrometer` vocabulary, coins no new Family, and adds a second consumer to each pending diffraction Method.

So the technique side of HEX earns no new abstraction. It reinforces, at a high-energy beamline, the case that energy-dispersive and powder diffraction belong in the catalog (`TECH-1`), the same earn-the-abstraction discipline 7-BM and i11 already follow. The device Roles exist (the cameras and the flat panel present Detector, the GeRM strip detector presents Sensor), so what stays pending is the science Capability, not a device shape. Because those Capabilities are not yet in the catalog, the matching Site Practices (`HEX_radiography_practice`, `HEX_energy_dispersive_diffraction_practice`, `HEX_powder_diffraction_practice`) are carried pending in the [NSLS-II Site](../nsls2/index.md#the-techniques-adapted-here); each binding lands when its Capability does. `HEX_tomography_practice` names the graduated `tomography` Method and renders linked.

## Multi-technique in one experiment, the distinct contribution

The structurally distinct thing about HEX is not any one technique; it is that imaging / tomography, EDXD, and ADXD are all available in the single F-hutch endstation during the same experiment, with detectors and optics moved into place remotely per technique. A high-energy beamline lets a user follow a working battery or a loaded engineering component and switch, within one mounting, between a tomographic view of the microstructure, an energy-dispersive map of internal strain and phase, and an angle-dispersive powder pattern.

CORA models this as **multiple Methods over one endstation**, not a new Capability. The switch itself is a positioning action: a [detector / optics stage](equipment/detector.md) moves the chosen detector into the beam. That positioning binds the catalog `LinearStage` and is conducted over the `ControlPort` (see [Controls](equipment/controls.md)); it is a Practice-level sequence, not a new technique. The one-technique-per-acquisition assumption is what this stresses, and the resolution is that a Run selects its technique by positioning, then acquires (`TECH-1`).

| Technique in the experiment | Detector | Family |
| --- | --- | --- |
| imaging / tomography | [Kinetix sCMOS](equipment/detector.md) + scintillator-lens | `Camera` + `Scintillator` |
| time-resolved radiography | [Phantom Veo](equipment/detector.md) | `Camera` |
| energy-dispersive diffraction (EDXD) | [GeRM strip detector](equipment/detector.md) | `EnergyDispersiveSpectrometer` |
| angle-dispersive diffraction (ADXD) | [PerkinElmer flat panel](equipment/detector.md) | `Camera` |

## Not modelled yet

The concrete acquisition recipes are not written yet. For tomography that is the fly-rotation step model, the dark / flat sequence (`tomo_dark_flat`), and the vertical stitch (`tomo_y_scan_loop`); the reconstruction (flat-field correction, ring / stripe removal) is `ComputePort` work, not a beamline Method. For diffraction it is the EDXD gauge-volume definition and the angle-dispersive integration that turns 2D frames into one-dimensional patterns. These join as the deployment approaches the point where CORA drives HEX.

Whether any of these techniques enters CORA's catalog is an owner-scope decision on [Model](model.md): a modelling exercise reinforces the case but does not mint cross-facility Method vocabulary on its own. HEX adds a second consumer to the pending `energy_dispersive_diffraction`, `radiography`, and `powder_diffraction` Methods, which strengthens the case for cataloging them but leaves that an owner decision (`TECH-1`). See [Open questions](questions.md) for the world-facts to confirm first, including whether pair-distribution-function (PDF) or three-dimensional X-ray diffraction (3DXRD) are offered, which public sources do not list for HEX (`TECH-1`).
