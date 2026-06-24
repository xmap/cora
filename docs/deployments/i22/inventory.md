# Inventory

*The CORA Asset model for I22: the planned device tree, the dodal-derived control handles, and what still needs confirming.*

I22 is a design-phase modelling exercise, so this is the planned Asset shape, not a registered inventory. It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages. The shape is generated-honest: it is authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i22/beamline.yaml) descriptor that the Source page renders from.

Unlike the other design-phase scaffolds, the **control handles are known**: Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) library records the real EPICS PV prefixes, so each device carries its handle. Devices bind to catalog [Families](../../catalog/families.md) where one fits. No vendor Model is bound: dodal names hardware (Dectris Pilatus3 2M, AVT Mako, Watson-Marlow, Linkam) but none is procured into the CORA catalog, so models are open questions, not bindings.

## The Asset tree

Root Asset `I22` (`tier = Unit`, `facility_code = diamond`); sub-systems nest below by `parent_id`. The families in bold are loose design-intent names not in the catalog yet (they render as plain text); each is tagged with the open question that decides whether it is earned into the catalog or folds into an existing Family plus settings. PV prefixes are the dodal-derived dry facts, carried `confirm` (a controls-library snapshot, to be verified against the live system).

| Asset | Family | Control handle (dodal) | Notes |
| --- | --- | --- | --- |
| `I22` | (root) | | bound to the Diamond Site |
| `Undulator` | InsertionDevice | `SR22I-MO-SERVC-01:` | undulator source; 80 poles, 2.0 m (dodal) |
| `StorageRing` | **StorageRing** | | machine-level, observe-only ring state; loose family |
| `DCM` | Monochromator | `BL22I-MO-DCM-01:` | double-crystal monochromator, Si(111) |
| `VFM` | Mirror | `BL22I-OP-KBM-01:VFM:` | vertical focusing mirror (KB pair) |
| `HFM` | Mirror | `BL22I-OP-KBM-01:HFM:` | horizontal focusing mirror (KB pair) |
| `BimorphHFM` | Mirror | `BL22I-OP-KBM-01:G0:` | adaptive bimorph, 12 channels (a setting on Mirror) |
| `BimorphVFM` | Mirror | `BL22I-OP-KBM-01:G1:` | adaptive bimorph, 32 channels |
| `Transfocator` | **Transfocator** | `BL22I-MO-FSWT-01:` | compound-refractive-lens transfocator; loose family |
| `Slit1`..`Slit6` | Slit | `BL22I-AL-SLITS-0N:` | beam-defining slits; five four-blade, one gap+centre |
| `SampleBase` | LinearStage | `BL22I-MO-STABL-01:` | sample base table (X/Y/PITCH) |
| `OAV` | Camera | `BL22I-DI-OAV-01:` | on-axis-view alignment camera (Mako G-507B) |
| `I0` | **FluxMonitor** | `BL22I-EA-XBPM-02:` | incident-flux ion chamber; presents the Sensor Role |
| `It` | **FluxMonitor** | `BL22I-EA-TTRM-02:` | transmitted-flux ion chamber; presents the Sensor Role |
| `SampleTemperature` | TemperatureController | `BL22I-EA-TEMPC-05:` | Linkam temperature controller; settable actuator (now a catalog Family, presents Regulator) |
| `SamplePump` | **FlowController** | `BL22I-EA-PUMP-01:` | peristaltic pump; settable actuator |
| `SaxsDetector` | Camera | `BL22I-EA-PILAT-01:` | Pilatus3 2M, 0.172 mm pixel, Si 0.45 mm (dodal) |
| `WaxsDetector` | Camera | `BL22I-EA-PILAT-03:` | second Pilatus3 2M at short camera length |
| `BeamStop1`..`BeamStop3` | BeamStop | `BL22I-MO-SAXSP-01:BSn:` | SAXS beamstops (positioned) |
| `Panda1`, `Panda2` | TimingController | `BL22I-EA-PANDA-0N:` | PandABox FPGA trigger/gate generation |

Reused catalog Families (no new Family needed): `InsertionDevice`, `Monochromator`, `Mirror`, `Slit`, `LinearStage`, `Camera`, `BeamStop`, `TimingController`. An adversarial new-kind review refuted all five proposed new kinds (`StorageRing`, `Transfocator`, `FluxMonitor`, `TemperatureController`, `FlowController`) as catalog Families on the strength of I22 alone, deferring each as a loose design-intent family. One has since graduated: `TemperatureController` reached the rule-of-three at i11 and is now a catalog Family presenting the `Regulator` Role (the Linkam here binds it). The rest stay loose, earned into the catalog only when a confirmed device and a rule-of-three settle them. This mirrors how 7-BM carries `Photodiode` / `FlowController` and TomoWISE carried `HeatAbsorber` / `SlipRing`.

## Pending confirmations

Every value below is reverse-engineered from dodal or inferred, awaiting the beamline team or a Diamond source. Each is tracked by an [open question](questions.md); the answer lands in the descriptor and the row is removed.

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Hutch PSS permit signals | both enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Which hutch each device sits in | all devices | `unknown-pending-confirmation` | (ENC-1) |
| Undulator energy range and gap-to-energy curve | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| Storage-ring state modelling boundary | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| Optic internal settings (coatings, d-spacing, bimorph calibration) | `VFM`, `HFM`, `BimorphHFM`, `BimorphVFM`, `DCM` | `unknown-pending-confirmation` | (OPT-1) |
| Transfocator modelling boundary (loose Family vs existing plus settings) | `Transfocator` | `unknown-pending-confirmation` | (CRL-1) |
| Detector camera lengths (fixed mount vs settable axis) | `SaxsDetector`, `WaxsDetector` | `unknown-pending-confirmation` | (DET-1) |
| Pilatus threshold energy and beam-center | `SaxsDetector`, `WaxsDetector` | `unknown-pending-confirmation` | (DET-2) |
| OAV working distance and effective pixel size | `OAV` | `unknown-pending-confirmation` | (OAV-1) |
| Flux-monitor modelling boundary and placement | `I0`, `It` | `unknown-pending-confirmation` | (FLUX-1) |
| Settable-actuator command path for sample environment | `SampleTemperature`, `SamplePump` | `unknown-pending-confirmation` | (ENV-1) |
| Scattering Capabilities and Methods in scope | techniques | `unknown-pending-confirmation` | (TECH-1) |
| Hardware identity (serial numbers, asset tags) | all devices | `unknown-pending-confirmation` | (ID-1) |

Assertion-style questions that do not leave a value blank (the scope question SCOPE-1, the triggering binding TRIG-1, and the Assembly-grouping question GROUP-1) are on [Open questions](questions.md) without a placeholder here.
