# Techniques

*What I22 is designed to do, as intent. Design-phase.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../diamond/index.md) is how a facility adapts it. I22 is the first scattering beamline CORA has looked at, so its techniques are the first that do not reduce to the existing tomography and acquisition Capabilities. Which scattering Capabilities and Methods the catalog earns is itself an open question (TECH-1); the function view below survives the eventual vocabulary choices, which is why it can be written before the catalog is extended.

| Technique | Beam | Detector | Status in CORA |
| --- | --- | --- | --- |
| Small-angle scattering (SAXS) | monochromatic, KB-focused | `SaxsDetector` (Pilatus3 2M, long camera length) | new Capability, pending (TECH-1) |
| Wide-angle scattering (WAXS) | monochromatic, KB-focused | `WaxsDetector` (Pilatus3 2M, short camera length) | new Capability, pending (TECH-1) |
| Simultaneous SAXS+WAXS | monochromatic, KB-focused | both detectors at once | coordinated Runs, the routine mode, pending (TECH-1) |
| Time-resolved SAXS/WAXS | monochromatic | both detectors, PandA-gated | new acquisition Method, deferred until confirmed |

A few points of intent shape the model:

- **The Capabilities are genuinely new.** Tomography reduces to the `tomography` and `acquisition` Capabilities the catalog already carries; SAXS and WAXS do not. They are the cleanest test of whether CORA's Capability layer generalizes past imaging. They are carried as pending Practices on the [Diamond Site](../diamond/index.md), not minted into the catalog, until the technique enters a real scope (TECH-1). A beamline that is a modelling exercise does not get to mint cross-facility vocabulary.
- **Simultaneous acquisition is coordinated Runs, not a combined technique.** The routine I22 mode reads the SAXS and WAXS detectors at once. CORA models that as coordinated Runs under one Campaign over a shared trigger, the same way 7-BM models energy-dispersive diffraction running alongside tomography, not as a third combined technique.
- **The detector Roles already exist.** Both detectors present the existing Detector Role; the flux monitors present the existing Sensor Role. No new Role is needed for scattering, only new science Capabilities. The device anatomy generalized cleanly; the technique vocabulary is what is new.
- **Beam mode is one focused, monochromatic path.** The undulator feeds the double-crystal monochromator and the KB mirror pair; SAXS and WAXS share that one conditioned beam, distinguished by detector position, not beam mode.

The concrete acquisition recipes (q-ranges, camera lengths, exposure, time-resolved sequences) are not written: they are calibration the deployment must supply. See [Open questions](questions.md) for what must be confirmed first.
