# Controls

*The control stack and the orchestration seam. ESRF BLISS, a Tango-based control system, NOT EPICS. ID16B is CORA's third non-EPICS deployment, after ID32 and ID19; this page shows the BLISS seam holding for a further beamline.*

ID16B runs the ESRF **BLISS** control system, built on **Tango**, the same non-EPICS floor as [ID19](../../id19/equipment/controls.md). The fleet's other deployments are all EPICS (ophyd / bluesky / dodal / pcdshub); ID19 was the first live non-EPICS floor, and ID16B is the second. A second beamline on the same floor is what turns the ID19 seam from a one-off into a pattern: CORA observes the BLISS floor and, where it replaces BLISS scan orchestration, conducts over it; it does not replace BLISS or Tango.

The handles on this page are real, read from ID16B's own public Beacon device database ([`gitlab.esrf.fr/id16b/beamline_configuration`](https://gitlab.esrf.fr/id16b/beamline_configuration)), and carried `confirm` because a config snapshot is strong evidence, not a guarantee against the live system (CTRL-1). The control Tango domain is `id16b` / `id16na`.

## How BLISS expresses a device

CORA models each device's control handle as an opaque string set at the edge; the handle does not care whether the floor is EPICS or BLISS, only its shape changes. From ID16B's config:

- **A motion stage** is a BLISS axis under a controller class: IcePAP racks (`iceid162` mono, `iceid164` sample / KB / slits / shutter), PI piezo scanners (`vscanner1` / `vscanner2`, E518), and etel Tango motors (the sample rotation `id16b/dsc2p/rot16`).
- **A fluorescence detector** is a MOSCA / FalconX Tango device (`id16b/moscav1/fxb`).
- **An area detector** is a Lima device server addressed by a Tango name (`id16na/limaccds/pco1`).
- **The monochromator** is the Kohzu DCM controller (`ID16Bkohzu`).

| Asset | Family | Handle | What it does |
| --- | --- | --- | --- |
| `InsertionDevice` | [`InsertionDevice`](../../../catalog/families.md) | `U205` (ESRF_Undulator) | the undulator source (SRC-1) |
| `Monochromator` | [`Monochromator`](../../../catalog/families.md) | `mono`/`Edcm` (Kohzu, iceid162) | the DCM (OPT-1) |
| `KBMirrors` | [`Mirror`](../../../catalog/families.md) | `kbx`/`cfocus`/`cfocus2` (iceid164) | the KB nanofocus (OPT-1) |
| `SampleRotation` | [`RotaryStage`](../../../catalog/families.md) | `id16b/dsc2p/rot16` (etel), `srot2` | the tomo / fluo-tomo rotation (SAMPLE-1) |
| `SampleScanner` | [`LinearStage`](../../../catalog/families.md) | `sampy`/`sampz` (PI piezo vscanner) | the nano-XRF raster (SAMPLE-1) |
| `FluoDetector` | [`EnergyDispersiveSpectrometer`](../../../catalog/families.md) | `id16b/moscav1/fxb` (FalconX) | the XRF detector (DET-1) |
| `TomoDetector` | [`Camera`](../../../catalog/families.md) | `id16na/limaccds/pco1` (Lima) | the area detector (DET-1) |

The motion controllers themselves are modelled as two `MotionController` Assets: the `IcePAPControllers` (`iceid162` / `iceid164`) and the `PiezoScanners` (the PI vscanner / E518 controllers driving the fine XRF raster). The full handle list, Asset by Asset, is in the [Inventory](../inventory.md), and the source walk is the generated [Source](../beamline.md) page.

What the config does **not** give, and so is not invented here:

- the PSS search-and-secure permit signals behind the shutters (PSS-1).
- the sample environments' control detail beyond noting they exist (ENV-1).
- vendor part numbers, serials, focal-spot sizes, and physical positions (carried confirm).

## The orchestration seam

Both ID16B acquisitions are BLISS scan procedures (the `daiquiri_tomo` and `daiquiri_fluo` / `fluo3d` sessions). Nano-tomography couples a continuous sample rotation to the area-detector frame capture; nano-XRF mapping couples a piezo raster to the fluorescence-detector readout. Those loops are the orchestration CORA's edge conducts over the same floor, driving through the BLISS device layer rather than BLISS owning the loop, with the conduct-versus-drive-through split decided per routine (CTRL-2).

This is CORA's third non-EPICS deployment, so the seam evidence compounds: the same edge that conducts a tomo scan over BLISS at ID19 conducts both a tomo scan and an XRF raster over BLISS at ID16B, against Lima detectors, a MOSCA fluorescence detector, and IcePAP / PI piezo axes. The `ControlPort` is the same; only the floor's device shapes differ. The techniques are plain reuse (`tomography`, `scanning_fluorescence_microscopy`); ID16B coins no new device family.

The downstream reconstructions are not beamline devices: the tomographic volume retrieval and the XRF map fitting are `ComputePort` work, run over the port rather than modelled as endstation Assets.

### The seam: CORA and the floor

CORA **owns** (its conducting engine, over the `ControlPort`):

- the nano-tomography acquisition (rotation coupled to area-detector capture) and the nano-XRF acquisition (piezo raster coupled to fluorescence readout);
- the choice of technique and timing, gated by the [trust boundary](../governance.md#the-trust-boundary).

CORA **drives through** (the floor it actuates and observes, and does not replace):

- the **BLISS / Tango** device layer: the stages (BLISS axes over IcePAP, PI piezo, etel Tango), the FalconX fluorescence detector (MOSCA Tango), the area detectors (Lima Tango), the Kohzu DCM, the `ControlPort` boundary;
- the detector file-writing to the ESRF data store. That is plumbing CORA observes; CORA moves the frames and spectra, over the `TransferPort`, into CORA's own Dataset of record.

So CORA brings one conducting engine to ID16B, working over the ports: the two acquisitions over the `ControlPort` (against BLISS, not EPICS), the volume / map reconstructions over the `ComputePort`, and data egress over the `TransferPort`. The reconstructions are clean `ComputePort` legs, not beamline devices (TECH-1, METHOD-1).

The BLISS / Tango device servers (the Lima and MOSCA detectors, the IcePAP and PI controllers) are referenced by interface only, never registered as Assets beyond the two `MotionController` handles.

## Equipment protection

The shutter handles are known from the config (the front-end and `fshut` fast shutter), but the PSS search-and-secure permit signals behind them are **not in the config** and are not invented here (PSS-1). CORA names the shutters but not the permit signals until the beamline team supplies them.

The Enclosure permit shape for the two hutches and the hazard tier are carried pending at the ESRF Site; the governance and safety envelope follow the 2-BM shape (see [Governance](../governance.md)). The ESRF operator pool and review are pending at the Site (GOV-1), and Clearances are issued at the ESRF Site.

See [Open questions](../questions.md) for the control, detection, and safety items still to confirm, and [Model](../model.md#deliberately-not-here-yet) for the deferred sample environments and why this nanoprobe deployment coins no new vocabulary.
