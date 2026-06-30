# Model

*The developer's index into where i06 content lives, why this first APPLE-II deployment coins no new family, how it models polarization as an axis, and the record of what is deliberately deferred. First cut.*

i06 is a descriptor-and-docs scaffold today, reverse-engineered from the beamline's dodal device layer: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/i06/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i06/beamline.yaml) | the device walk with bound PVs; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/diamond/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/diamond/site.yaml) | the Diamond facility surface; `I06` added to its beamline list, with XMCD / XMLD / PEEM / resonant-diffraction Practices |
| Extraction provenance | [DiamondLightSource/dodal](https://github.com/DiamondLightSource/dodal) | the `src/dodal/beamlines/i06*.py` factories and `src/dodal/devices/` classes the descriptor was curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; every device reuses an existing catalog or loose Family (below) |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; the XMCD / XMLD / PEEM / resonant-scattering Methods are pending (TECH-1, PEEM-1) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers i06 Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes i06 new

i06 is CORA's first APPLE-II (variable-polarization) source. The fleet's other insertion devices set a gap; an APPLE-II additionally drives its magnetic phase rows to choose the X-ray polarization, so i06 is the first beamline whose run sets the polarization as an experiment axis: linear horizontal or vertical, linear at an arbitrary angle, circular positive or negative, and third-harmonic variants. That is what magnetic dichroism needs (the X-ray magnetic circular and linear dichroism contrast comes from flipping or rotating the polarization at an absorption edge). i06 is also CORA's first PEEM (photoemission electron microscopy) endstation, an electron-imaging technique distinct from the electron-energy analysis of ARPES.

The novelty forces no new device families. It is carried by two reuse decisions and two deferrals (below). The genuinely new modelling primitive, polarization as a driven axis, is expressed by reusing the existing `PseudoAxis` Family, the same way incident energy is already a pseudo-axis.

## No new families

i06 coins no new Family and changes nothing in the catalog. The four devices that could have tempted a new kind all fold into existing vocabulary:

- **The two APPLE-II undulators bind the catalog `InsertionDevice`, not a new source family.** An APPLE-II is the same source-undulator anatomy as the EPUs already bound by SIX, CSX, and ESM. The catalog `InsertionDevice` Family already "spans the undulator and the wiggler; the device type and its gap / field parameters are a per-Asset settings difference." The APPLE-II variable-polarization phase rows, the EPICS energy-to-gap polynomial lookup, and the coordinating controller are per-Asset settings and the bound Model (they are how the gap and phase are driven), not a new device class. This resolves the long-standing `SRC-1` question toward reuse: a second concordant variable-polarization source confirms the existing Family stretches, rather than earning a split.

- **Polarization is a `PseudoAxis`, not a new primitive.** The thing an i06 run sets, the polarization, is modelled as a `PseudoAxis` Asset, a sibling of the incident-energy pseudo-axis over the same source. The polarization value domain (LH / LV / PC / NC / LA plus third-harmonic variants) is the axis's value set, and the controller's polarization-to-phase conversion is its partition rule. This is exactly the 2-BM beam-energy-as-pseudo-axis precedent, extended to a second driven source quantity. CORA names the axis, writes the value, and records the move; by default the live i06 controller owns the polarization-to-phase kinematics (the partition rule is carried rule-less, `POL-1`), so CORA does not duplicate a second source of truth for the optics geometry.

- **The PEEM sample manipulators bind the graduated `Manipulator`.** The PEEM endstation's UHV sample manipulators (x / y / phi plus the energy-slit translation) reuse the `Manipulator` Family graduated on SIX and ESM; the energy-slit axis and axis count are per-Asset settings.

- **The PGM binds `GratingMonochromator`, the diffractometer binds `Goniometer`, the Lakeshores bind `TemperatureController`.** All three reuse families the soft X-ray and diffraction siblings already earned.

## Deliberately not here yet

- **The PEEM electron-imaging column and detector (`PEEM-1`).** The PEEM technique's defining instrument, the electron-optical column that forms a magnified electron image of the photoemitting surface, is not a dodal device (dodal binds the PEEM sample manipulator and its energy slit, not the column or the image detector). It is the `ElectronMicroscope` anatomy: an electron-imaging column, distinct from the photon `Camera` (which produces a Frame from photons) and from the energy-analyzing catalog `ElectronAnalyzer` (the ESM / ARPES electron-energy analyzer). It is deferred as `PEEM-1`, not coined: binding a family with no PV would create an orphan, so the column and detector land once their handles are sourced. i06's PEEM branch is then a candidate first sighting for an `ElectronMicroscope` family.

- **The i06-1 diffraction detector and the flux monitors (`DET-1`).** The i06-1 scattering detector and any incident-flux or drain-current (electron-yield) monitor are absent from dodal (only the detector-arm motors are present). The geometry is modelled now; the detectors are bound later from outside dodal, and no detector Family is invented in the meantime.

- **The diffractometer Assembly (`DIFF-1`).** Whether the i06-1 sample circles plus the detector arm compose an `Assembly(Diffractometer)` is deferred, exactly as 4-ID, 8-ID, and CSX deferred materializing their soft X-ray diffractometer Assemblies in descriptor mode. The first cut is a flat `Goniometer` Asset plus a reciprocal-space `PseudoAxis`, with the Assembly named as the follow-on.

- **The XMCD / XMLD / PEEM Methods.** Whether magnetic dichroism, photoemission microscopy, and resonant soft X-ray diffraction enter CORA's catalog as Capabilities / Methods is an owner decision; the Practices render unlinked, pending. XMCD and resonant scattering share the 4-ID POLAR Methods; XMLD and photoemission microscopy are new pending slugs (`TECH-1`, `PEEM-1`).

- **The polarization Calibration (`POL-1`).** Pinning the polarization-to-phase conversion as a CORA-owned LookupTable Calibration revision (rather than letting the live i06 controller own it) is deferred; it is only needed if CORA must scan polarization without the i06 controller in the loop.

- **The simulated devices and full asset-tree scenarios.** No `test_i06_*.py` registers the asset tree, and no vendor Models are bound. Those land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
