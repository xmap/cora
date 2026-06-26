# Techniques

*What CORA would run at I20-1: energy-dispersive EXAFS, a [Catalog](../../catalog/methods.md) Method bound through a [Diamond Practice](../diamond/index.md). It is the dispersive complement to the scanning-XAS axis, and its Capability is deferred, the more so because the dispersive devices are not yet in source.*

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Energy-dispersive EXAFS (EDE) | `energy_dispersive_exafs` | the whole absorption spectrum read in one shot off a polychromatic fan on a strip detector; time-resolved. New Capability, pending (TECH-1); the dispersive polychromator + strip detector are not yet in source (POLY-1 / STRIP-1) |
| Fluorescence-yield EXAFS | `energy_dispersive_exafs` | the same dispersive acquisition read in fluorescence on the Xspress3, a secondary mode (DET-1) |

The technique is recorded as a pending [Practice](../diamond/index.md) on the Diamond Site.

## Why the Capability is deferred (and the heart is an open question)

EDE is a new science Capability for CORA: scanning XAS (NSLS-II BMM) steps a monochromator through an edge and the per-energy readings are the data, while EDE reads every energy at once off a dispersed fan. CORA carries the EDE Method as pending, the dispersive complement to the energy-scan question BMM opened (TECH-1 / the ENERGY-1 cohort), rather than coining it, the same earn-the-abstraction discipline every new-domain technique follows.

The sharper point at I20-1 is that the two devices the Capability turns on, the bent-crystal polychromator and the position-sensitive strip detector, are not in the public dodal commissioning module. So this is a partial first cut: the technique is named and its periphery modelled (the energy-selecting turbo slit, the fly-scan PMAC and PandA timing, the fluorescence Xspress3), but the dispersive optic and detector are explicit open questions (POLY-1, STRIP-1). The polychromator in particular would be a genuinely new optic class, an energy-fanning bent crystal distinct from a `Monochromator`, that CORA would weigh as a Family once it is PV-bound; coining it now, with no source PV, would be invention.

The spectrum extraction (turning the dispersed strip frame into an absorption spectrum) is `ComputePort` work, not a beamline Method.
