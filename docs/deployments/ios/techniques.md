# Techniques

*What CORA would run at IOS: ambient-pressure photoemission and soft X-ray absorption, each a [Catalog](../../catalog/methods.md) Method. IOS follows the deferral discipline of the soft X-ray beamlines that brought each technique family to CORA. First cut.*

IOS's techniques are soft X-ray surface science under working conditions: ambient-pressure photoemission and soft NEXAFS / XAS. The Methods below render unlinked and are carried pending until the owner-scope decision (`TECH-1`) brings them into the catalog. Following [SST](../sst/techniques.md), IOS records **no Practice** at the [NSLS-II Site](../nsls2/index.md#the-techniques-adapted-here) yet, because each technique sits on a pending or deferred Method; each binding lands when its Capability does.

| Technique | Mode | Notes |
| --- | --- | --- |
| Ambient-pressure photoemission (AP-XPS / AP-PES) | fixed energy, gas atmosphere | photoelectron spectra on the SPECS hemispherical analyzer under a working gas pressure; the ESM / SST photoemission family, new Capability pending (`TECH-1`) |
| Soft NEXAFS / XAS | energy sweep | absorption by total / partial electron yield (drain current through the scaler) and partial fluorescence yield (the Vortex / Xspress3), over a PGM energy scan; the BMM energy-scan question (`ENERGY-1`, `TECH-1`) |

Both need the [grating monochromator](beamline.md) (the incident energy), the [AP-PES manipulator](equipment/sample.md) (the sample in the analyzer focus), and the [analyzer and yield chain](equipment/detector.md). The detection mode (TEY drain current, PEY kinetic-energy-selected electrons through the analyzer, PFY region-of-interest fluorescence) is a setting, not a separate technique.

## Why the Capabilities stay deferred

Each of IOS's techniques sits on a Capability the catalog does not yet carry, and the discipline is the same one the originating beamlines applied:

- **Ambient-pressure photoemission** follows NSLS-II [ESM](../esm/index.md). The only photoemission Method slug the catalog anticipates is `angle_resolved_photoemission`, coined for ESM's ARPES; IOS's AP-XPS is chemical-state photoemission under a gas atmosphere, not angle-resolved, so reusing that slug would name a shape it was not coined for. The device Role already exists (the analyzer presents Detector); what is new is the science Capability, and the ambient-pressure context on top of it.
- **Soft NEXAFS / XAS** follows [BMM](../bmm/index.md): the measurement is the energy sweep itself, the deferred `energy_scan` Capability (`ENERGY-1`). It is a different shape from the crystal-emission-spectrometer `xas_spectroscopy` that LCLS-MFX and ISS left pending (which disperses emitted photons through an analyzer crystal); IOS's NEXAFS reads absorption by electron and fluorescence yield.

So IOS reinforces both technique families at one more instrument without coining either, and records no Practice; each binding lands when its Capability does (`TECH-1`, `ENERGY-1`).

## The ambient-pressure context

What distinguishes IOS from the fleet's other photoemission and absorption beamlines is that it runs under a working gas atmosphere (in situ / operando), not in vacuum. That context is the heart of the science, but the hardware that delivers it (the reaction cell, the gas dosing and mixing, the pressure control, the sample heating) is not in the profile collection and is carried as the headline open question (`INSITU-1`), not modelled. When a Method for ambient-pressure spectroscopy is eventually authored, the ambient-pressure context would be a Practice-level adaptation (the gas, pressure, and temperature settings) on the photoemission and absorption Methods, not a separate technique.

## Not modelled yet

The concrete acquisition recipes (the energy scans with their coupled EPU edge-table switching, the spectrum acquisitions, the yield reads) are not written yet; they join as the deployment approaches the point where CORA drives IOS. The per-technique reduction (photoemission spectra, NEXAFS spectra) is `ComputePort` work, not beamline Methods. See [Open questions](questions.md) for the world-facts to confirm first.
