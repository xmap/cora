# Model

*The developer's index into where i10 content lives, why this second APPLE-II deployment coins no new family, what it decides at two loose families' second sighting, and the record of what is deliberately deferred. First cut.*

i10 is a descriptor-and-docs scaffold today, reverse-engineered from the beamline's dodal device layer: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/i10/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i10/beamline.yaml) | the device walk with bound PVs; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/diamond/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/diamond/site.yaml) | the Diamond facility surface; `I10` added to its beamline list, with resonant-scattering / reflectivity / XMCD / XMLD Practices |
| Extraction provenance | [DiamondLightSource/dodal](https://github.com/DiamondLightSource/dodal) | the `src/dodal/beamlines/i10*.py` factories and `src/dodal/devices/` classes the descriptor was curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; every device reuses an existing catalog or loose Family (below) |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; the resonant-scattering / reflectivity / XMCD / XMLD Methods are pending (TECH-1) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers i10 Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes i10 new

i10 is the fleet's second APPLE-II (variable-polarization) source, after i06, and it is i06's soft X-ray twin: the same shared spine of twin APPLE-II undulators feeding a plane-grating monochromator and two branch endstations. What i10 adds is the science those endstations do with the polarization: resonant soft X-ray scattering and reflectivity on the RASOR diffractometer (with a polarization-analysis arm that resolves the polarization of the scattered beam), and X-ray magnetic dichroism with the sample in an applied magnetic field at the i10-1 endstation.

For the modelling, i10's significance is that it brings two device families that were loose at a single beamline (4-ID) to a second sighting: the polarization analyzer and the sample-environment magnet. Reaching a second independent deployment is the point at which CORA records a deliberate hold-or-graduate decision (below). i10 holds both, and coins no new family.

## No new families

i10 coins no new Family and changes nothing in the catalog.

- **The polarization decisions follow the merged i06 precedent.** The two APPLE-II undulators bind the catalog `InsertionDevice` (the phase rows, the energy-to-gap polynomial, and the controller are per-Asset settings and the bound Model). The polarization is a `PseudoAxis` Asset, a sibling of the incident-energy axis over the same source; the Pol value domain (LH / LV / PC / NC / LA plus third-harmonic variants) is the axis's value set, and the controller's polarization-to-phase conversion is its partition rule, carried rule-less (`POL-1`). i10's one addition over i06 is the continuous linear-arbitrary-angle: it is the continuous realization of the LA value within the same polarization axis, not a second axis, since the angle is meaningful only as a refinement of LA.
- **The RASOR sample circles bind `Goniometer`, with a reciprocal-space `PseudoAxis`** (the 4-ID / 8-ID / i06-1 diffractometer pattern; the Assembly is named, not built, `DIFF-1`).
- **The rest reuse existing families:** the PGM binds `GratingMonochromator`; the collimating, switching, and focusing mirrors bind `Mirror`; the slits bind `Slit`; the pinhole binds `Aperture`; the sample and magnet stages bind `LinearStage`; the Lakeshore controllers bind `TemperatureController`; and the counting chains bind `FluxMonitor`. The machine state reuses the loose `StorageRing`.

## Loose families at a second sighting

Two loose families that were used only at 4-ID reach their second sighting at i10. The promotion guard (`PROMOTION_THRESHOLD = 2`) makes a loose family used by two or more deployments require a recorded hold-or-graduate decision: the signal is mechanical, the decision stays human. i10 records both as **hold**, not graduate, because the rule-of-three (a genuine third, independent sighting that confirms the abstraction across facilities) is not yet met and graduation is a catalog-scope change.

| Loose family | Sightings | i10 binding | Decision |
| --- | --- | --- | --- |
| `PolarizationAnalyzer` | 4-ID, i10 (RASOR PaStage) | the RASOR polarization-analysis arm (the POLAN stage) | **hold** (`POL-2`): a genuine second sighting of a polarization analyzer; dodal exposes the analyzer arm's motors only (the analyzer crystal is implicit hardware), so CORA models the role on the real motorized arm and tees up the rule-of-three rather than graduating at n=2 |
| `Magnet` | 4-ID, i10 (i10-1) | the i10-1 electromagnet and the superconducting field-sweep magnet | **hold** (`MAG-1`): both magnet devices are one Family, the field-sweep capability is a per-Asset bound-Model affordance, not a split (the `InsertionDevice` / `TemperatureController` precedent); held pending a third independent magnet deployment |

The decision to bind the RASOR PaStage to `PolarizationAnalyzer` (rather than to a plain detector-arm `RotaryStage` with the analyzer as a setting) is a deliberate one: RASOR's defining role is polarization analysis (the PV root is `POLAN`), and CORA models that role on the real arm rather than hiding it in a note. The absence of an analyzer-crystal signal in dodal is an absence in the data, not proof the role is absent; if staff confirm the analyzer operation, `POL-2` is the trigger for the third-sighting graduation decision.

## Deliberately not here yet

- **No area detector; the science detector is a point counter (`DET-1`).** Neither endstation has an area detector in dodal. Detection is point and current-integrating: the scattered-beam point detector, the incident-flux monitor, and the fluorescence and drain-current / total-electron-yield channels are current-amplifier-plus-scaler chains, which bind `FluxMonitor`. Whether scattered-beam point-counting eventually earns its own Sensor Family is `DET-1`; if a future i10 area detector appears, the science detector migrates.
- **The diffractometer Assembly (`DIFF-1`) and the reciprocal-space rule (`DIFF-2`).** Named, not built, exactly as 4-ID, 8-ID, and i06-1 deferred theirs.
- **The polarization Calibration (`POL-1`).** Pinning the polarization-to-phase and the linear-arbitrary-angle conversion as a CORA-owned Calibration is deferred; it is only needed if CORA must scan polarization without the i10 controller in the loop.
- **The resonant-scattering / reflectivity / XMCD / XMLD Methods.** Whether they enter CORA's catalog is an owner decision; the Practices render unlinked, pending. Resonant scattering and XMCD share the 4-ID Methods, XMLD shares the i06 slug, and reflectivity is a new pending slug (`TECH-1`).
- **The upstream diagnostics and simulated devices.** The diagnostic screens (d1-d7 fluorescent screens and webcams) and the simulated devices are not modelled in this cut; no `test_i10_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
