# Techniques

*What the modelled part of i19 is designed to do, as intent. Design-phase.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../diamond/index.md#the-techniques-adapted-here) is how a facility adapts it. i19 is CORA's first *chemical* crystallography beamline: small-molecule single-crystal structure solution, distinct from the macromolecular MX (I03, I24, FMX, MX3) the rest of the fleet carries. The function view below is written before the Method is coined, because it survives the eventual catalog vocabulary choice.

## Single-crystal diffraction

The Newport kappa four-circle goniometer orients a single crystal in the monochromatic or variable-wavelength beam, sweeps reciprocal space, and the Eiger records the scattered intensity as a function of momentum transfer. This is the same diffraction function the magnetic single-crystal stations already do; what differs at i19 is the science the data feed, not the recipe.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Single-crystal diffraction | `diffraction` | reciprocal-space scans on the kappa four-circle with the Eiger; shares the 4-ID / 8-ID / CSX `diffraction` Method, pending (TECH-1) |
| Variable-wavelength diffraction | `diffraction` | the same Method over a coordinated energy move; a Plan / settings difference, not a new Method (TECH-1) |

This needs the [diffractometer](equipment/sample.md) (the kappa four-circle, plus the 2-theta detector arm and det_z), the [Eiger detector](equipment/sample.md), and the shared-optics energy control. A few points of intent shape how the Method binds here:

- **Single-crystal diffraction reuses the pending `diffraction` Method.** The prior consumers are the magnetic single-crystal stations (4-ID, 8-ID, CSX); i19 is a fourth consumer of the same recipe. The Method binds a Goniometer that orients the crystal and a Camera that captures the diffracted frames. Chemical crystallography (small-molecule structure solution) versus the magnetic single-crystal science at 4-ID is a **Practice-level** difference, not a Method-level one: the I19_diffraction_practice (pending) is where the chemical adaptation lives, over the portable diffraction Method (TECH-1).
- **The kappa four-circle is plain Goniometer reuse.** kappa is a setting per the catalog Goniometer note, so the four-circle does not earn a new Family. The larger four-circle (phi / omega / kappa, the 2-theta arm, det_z, sample-centring) is the named-not-built `Assembly(Diffractometer)` composed over that Goniometer (DIFF-1). The reciprocal-space coordination binds `PseudoAxis` (DIFF-2).

## Serial / microfocus fixed-target delivery

i19 carries a serial / microfocus fixed-target arm: a second sample stage (x / y / z / phi) that presents many crystals to a microfocused beam on a fixed target. This is a **delivery sub-mode** of single-crystal diffraction, not a separate technique. It binds the same `diffraction` Method, with the second stage modelled as a second Goniometer (SERIAL-1).

| Delivery | Catalog method | Notes |
| --- | --- | --- |
| Fixed-target serial collection | `diffraction` | many crystals on the serial stage; the same Method, a delivery sub-mode (SERIAL-1) |

The one part that reaches past the present catalog is the **raster**: stepping the fixed target through a grid of positions and collecting at each would touch a grid-scan-style Method the catalog does not yet carry. Until that Method exists, the raster is carried as a note on the serial sub-mode, not modelled as its own recipe (SERIAL-1). The microfocused beam is shaped by the [MAPT pinhole and collimator](equipment/sample.md), whose aperture sizes are a Capability settings schema (the i03 MAPT precedent) (APERTURE-1).

## Not modelled yet

The concrete acquisition recipes are deferred: oscillation and scan ranges, exposures, the variable-wavelength sequence, and the serial raster pattern are calibration the deployment must supply, and writing them now for an unmodelled beamline would be invention, not record. They join as the deployment approaches the point where CORA drives i19.

Whether the `diffraction` Method (and the grid-scan-style Method the raster would need) enters CORA's catalog at all is an owner-scope decision, recorded on [Model](model.md); the raster's catalog gap is SERIAL-1 and the Method-coin question is TECH-1. See [Open questions](questions.md) for the world-facts to confirm first, including which hutch holds the four-circle (ENC-1).
