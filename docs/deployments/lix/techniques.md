# Techniques

*What the modelled part of LIX is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../nsls2/index.md#the-techniques-adapted-here) is how a facility adapts it. LIX measures biological structure three ways: biological solution scattering (bio-SAXS / WAXS), in-line size-exclusion-chromatography-coupled scattering (SEC-SAXS), and scanning-microbeam mapping of cells and tissue. The Methods below render unlinked and are carried pending until the owner-scope decision (`TECH-1`) brings any of them into the catalog.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Biological solution scattering (bio-SAXS / WAXS) | `solution_scattering` | small- and wide-angle scattering from a protein in solution in the [flow cell](equipment/sample.md), read on the [SAXS Pilatus 1M](equipment/detector.md); the fleet's first solution-scattering Method, new to the catalog (`TECH-1`) |
| In-line SEC-SAXS | `solution_scattering` | the [HPLC delivery pump](equipment/sample.md) flows an eluting size-exclusion peak through the cell while the SAXS detector reads; the same `solution_scattering` Method with the chromatographic elution as the acquisition axis (`TECH-1`, `FLUID-1`) |
| Scanning-microbeam mapping | `scanning_fluorescence_microscopy` | raster the microbeam across a cell or tissue section on the [scanning goniometer](equipment/sample.md), reading scattering and fluorescence per point; reuses the existing pending Method (`TECH-1`) |

All three techniques need the [incident-beam chain](beamline.md) (the undulator and DCM for energy, the mirrors and transfocator for focus, the slits), the [sample side](equipment/sample.md) (the positioning stack or scanning goniometer, and for the solution modes the fluidic delivery chain), and the [endstation detectors](equipment/detector.md) (the Pilatus heads, beamstop, flux monitors).

## Where the novelty is: the Subject, not the Method

LIX's measurement, small- and wide-angle X-ray scattering, is a science axis the fleet already speaks. The materials-scattering beamlines [SMI](../smi/techniques.md), [CMS](../cms/techniques.md), Diamond [I22](../i22/techniques.md), and APS [9-ID](../9-id/techniques.md) / [12-ID-E](../12-id-e/techniques.md) all run small- and wide-angle scattering on the same `Camera` / `FluxMonitor` / `BeamStop` vocabulary. So the scattering hardware and detection are reinforcement, not novelty.

What LIX adds is a new **Subject** and a new **sample-delivery** shape, not a new detector. The specimen is a protein in solution rather than a solid mount, and for SEC-SAXS it is an eluting chromatographic peak whose elution profile is the acquisition axis. That is why `solution_scattering` is proposed as a Method distinct from the materials `small_angle_scattering`: not because the optics differ, but because the Subject and the acquisition (a flowing, time-resolved liquid correlated to chromatography) differ. Whether the catalog ultimately holds one scattering Capability with solution-versus-solid as a Practice adaptation, or a distinct `solution_scattering` Capability, is the owner-scope decision (`TECH-1`); LIX records the case, it does not mint the vocabulary.

The matching Site Practices (`LIX_solution_scattering_practice`, `LIX_sec_saxs_practice`, `LIX_microbeam_scanning_practice`) are carried pending in the [NSLS-II Site](../nsls2/index.md#the-techniques-adapted-here); each binding lands when its Capability does.

## SEC-SAXS is a Procedure over the fluidic seam

In-line SEC-SAXS is the technique that most exercises the fluidic delivery chain, and CORA models it as a **Procedure**, not a new device. The run equilibrates the size-exclusion column, injects the sample, and reads SAXS frames continuously while the peak elutes through the [flow cell](equipment/sample.md). The actuators it drives, the [HPLC delivery pump](equipment/sample.md) (the graduated `FlowController`) and the selector valves (the seam), are conducted over the `ControlPort`; the [column and buffers](equipment/sample.md) are Supply; the eluting peak is a Subject; the frames correlated to the elution are the Dataset. The technique's identity in CORA's record lives in the Subject, Supply, and Procedure, not in a device or a new detector (`FLUID-1`, `SEC-1`, `SUBJECT-1`).

## Not modelled yet

The concrete acquisition recipes are not written yet. For solution scattering that is the per-frame exposures, the buffer-subtraction sequence, and the azimuthal integration that turns 2D frames into I(Q) curves (the integration and reduction are `ComputePort` work, not beamline Methods). For SEC-SAXS it is the column-equilibration and injection steps, the flow program, and the peak-fraction model that maps frames to elution. For the scanning mode it is the raster trajectory and the per-point reduction. These join as the deployment approaches the point where CORA drives LIX.

Whether any of these techniques enters CORA's catalog is an owner-scope decision on [Model](model.md): a modelling exercise reinforces the case but does not mint cross-facility Method vocabulary on its own. See [Open questions](questions.md) for the world-facts to confirm first.
