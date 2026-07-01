# I-TOMCAT

*Insertion-device tomographic-microscopy beamline at the Swiss Light Source (SLS 2.0). This page walks the beamline as CORA would model it; everything here is read from PSI's public pages and the SLS 2.0 design reports, not a CORA measurement.*

| Property | Value |
| --- | --- |
| Asset | `I-TOMCAT` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PSI](../psi/index.md) (Swiss Light Source storage ring; bound via `facility_code = "psi"`, `FacilityKind = Site`) |
| Sector | `X02SA` |
| Status | Reverse-engineered (modelled from public pages + design reports) |
| Source | U15 undulator (planned HTSU10 upgrade in 2027) |
| Control stack | SLS EPICS at the floor; BEC (Beamline and Experiment Control) scan layer over ophyd; device handles not public |

!!! warning "Modelling exercise, not a connection"
    I-TOMCAT is an off-roadmap modelling exercise. It is a hybrid: the TOMCAT instrument facts are modelled from PSI's public beamline pages and the SLS 2.0 design reports (the [TomoWise](../tomowise/index.md) "modelled from design report" tradition), because no public per-beamline controls config exists for TOMCAT. Every value on these pages is carried `confirm` until the beamline team verifies it. What CORA needs the team to confirm is collected on [Open questions](questions.md).

## Why I-TOMCAT

Under the SLS 2.0 upgrade the single legacy TOMCAT beamline was rebuilt as two complementary beamlines: **I-TOMCAT** (`X02SA`, the U15 undulator branch, this page) and **S-TOMCAT** (`X02DA`, a 5 T superbend, 8-80 keV including white beam; not modelled here). I-TOMCAT is the closest analog in the fleet to the APS [2-BM](../2-bm/index.md) micro-CT pilot: an undulator source, a multilayer monochromator, absorption and propagation-based phase-contrast tomography, an air-bearing rotation stage, a visible-light microscope over a scintillator, and the PSI in-house GigaFRoST camera for fast and dynamic 4D tomography. It is the natural first SLS beamline because the tomography model is the one CORA knows best.

## The beamline

The systems in three areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

Along the beam, in order:

- [Source](beamline.md): the beam delivery (the U15 undulator, the double-crystal multilayer monochromator, the diamond window, the filter batteries and focusing mirror, the safety shutter), rendered as the generated source-stage device walk.
- [Sample](equipment/sample.md): the I-TOMCAT endstation (ES2, ~33 m), the air-bearing rotation stage, sample positioning, the continuous-rotation slip ring, and the sample-side fast shutter.
- [Detector](equipment/detector.md): the visible-light microscope over a scintillator coupling to the high-speed camera suite, including the PSI GigaFRoST streaming camera.

Cutting across all three:

- [Controls](equipment/controls.md): the SLS EPICS floor and the BEC scan/orchestration layer, and where CORA's edge replaces it.

The cross-cutting reference view is the [Inventory](inventory.md): the planned Asset tree by `parent_id` with families and the values still pending confirmation. The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i-tomcat/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what I-TOMCAT is designed to do, as design intent. Each is a portable [Catalog](../../catalog/methods.md) Method that a PSI [Practice](../psi/index.md#the-techniques-adapted-here) would adapt once the deployment is live.

## Governance

[Governance](governance.md): who would act at I-TOMCAT and the trust shape that gates their commands. People and agents are facility principals at the [PSI Site](../psi/index.md#safety-and-governance).

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's I-TOMCAT content lives.

## Not yet documented

I-TOMCAT is a modelling exercise, so the operations runbook (procedures, recipes, cautions) and the live experiment view are deliberately not written yet: a runbook modelled from public pages without staff confirmation would be invention, not record. They join these pages if the deployment firms toward a real connection. The [2-BM](../2-bm/index.md) deployment shows the shape they will take.
