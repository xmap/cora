# Controls

*The control stack and the orchestration seam. ESRF BLISS, a Tango-based control system, NOT EPICS. This is CORA's first imaging deployment on the BLISS floor, and the page that carries its whole reason for existing.*

ID19 runs the ESRF **BLISS** control system, which is built on **Tango**. This is the first thing to say plainly, because it is what makes ID19 different from most beamlines CORA has modelled: the APS, Diamond, NSLS-II, and SLAC deployments are all EPICS (ophyd / bluesky / dodal / pcdshub). ID19's ESRF sibling ID32 opened the BLISS floor for CORA on soft X-ray RIXS; ID19 is the first to bring it to tomographic imaging. CORA observes that floor and, where it replaces BLISS scan orchestration, conducts over it; it does not replace BLISS or Tango.

The handles on this page are real. They are read from ID19's own public Beacon device database ([`gitlab.esrf.fr/id19/beamline_configuration`](https://gitlab.esrf.fr/id19/beamline_configuration), the live `/users/blissadm/local/beamline_configuration` YAML tree), and carried `confirm` because a config snapshot is strong evidence, not a guarantee against the live system (CTRL-1).

## How BLISS expresses a device

CORA models each device's control handle as an opaque string set at the edge, and that abstraction is exactly what ID19 tests: the handle is opaque, so it does not care whether the floor underneath is EPICS or BLISS. What changes is the *shape* of the handle. From ID19's config:

- **A motion stage** is a controller `class:` with named `axes:` (each axis a `name`, `steps_per_unit`, `velocity`, `acceleration`, limits, `unit`). The BLISS analogue of an EPICS motor record. ID19's stages are driven by **Elmo** serial controllers (the rotation stages `mrsrot` / `hrsrot`) and **IcePAP** racks (`iceid191` through `iceid195`, the sample / detector / slit / attenuator axes). CORA models the stage Asset, not the per-axis tuning.
- **A detector** is a Lima device server (`LimaCCDs`) addressed by a **Tango name**, `domain/family/member` (e.g. `id19/limaccd/frelon1`). This is the role an EPICS areaDetector PV root plays at the EPICS beamlines.
- **A shutter** is a `TangoShutter` addressed by a Tango name (`id19/bsh/1`).
- **The insertion-device source** is an `ESRF_Undulator` over a Tango master (`//acs.esrf.fr:10000/ID/MASTER/ID19`).

| Asset | Family | Handle | What it does |
| --- | --- | --- | --- |
| `InsertionDevices` | [`InsertionDevice`](../../../catalog/families.md) | `u13a_gap` ... `w150b_gap` (ESRF_Undulator) | the straight-section source set (SRC-1) |
| `Monochromator` | [`Monochromator`](../../../catalog/families.md) | `TripleMono` (Id19Mono) | triple monochromator, Bragg + Laue + multilayer (OPT-1) |
| `PrimarySlits` / `SecondarySlits` | [`Slit`](../../../catalog/families.md) | `psu/psd/...`, `ssu/ssd/...` | beam-defining slits |
| `Transfocator` | [`Transfocator`](../../../catalog/families.md) | `id19wbtfctrl` (ID19Transfocator) | white-beam Be-lens transfocator (OPT-1) |
| `Attenuators` | [`Filter`](../../../catalog/families.md) | `wba1`, `wba2` (WhiteBeamAttenuator) | white-beam attenuator banks (OPT-1) |
| `FrontEndShutter` / `BeamShutter1` / `BeamShutter2` | [`Shutter`](../../../catalog/families.md) | `//acs.esrf.fr:10000/fe/master/id19`, `id19/bsh/1`, `id19/bsh/2` | front-end and beam shutters (PSS-1) |
| `MR_RotationStage` / `HR_RotationStage` | [`RotaryStage`](../../../catalog/families.md) | `mrsrot` (Elmo), `hrsrot` (Elmo_whistle) | the tomographic spins (SAMPLE-1) |
| `MR_SampleStage` / `HR_SampleStage` | [`LinearStage`](../../../catalog/families.md) | `mrsx/mrsy/...`, `hrsx/hrsy/...` (IcePAP) | sample centring (SAMPLE-1) |
| `MR_Detector` / `HR_Detector` | [`Camera`](../../../catalog/families.md) | `id19/limaccd/frelon1`, `.../pco4k`, `.../dimax_*`, `.../basler1` | the Lima area detectors (DET-1) |
| `MR_DetectorStage` / `HR_DetectorStage` | [`LinearStage`](../../../catalog/families.md) | `hdx/hdy/hdz`, `hrxc/hryc/hrzc` (IcePAP) | the propagation-distance stages (DET-1) |

The motion controllers themselves are modelled as two `MotionController` Assets: the `ElmoControllers` (driving the rotation stages over serial / Tango serialrp) and the `IcePAPControllers` (the `iceid191-195` racks). The full handle list, Asset by Asset, is in the [Inventory](../inventory.md), and the source walk is the generated [Source](../beamline.md) page.

What the config does **not** give, and so is not invented here:

- the PSS search-and-secure permit signals behind the shutters: the TangoShutter handles are known, the permit signals are not (PSS-1).
- vendor part numbers, serials, energy ranges, and physical positions (carried confirm).
- the further endstations' device rosters (MH, MED, laminography, radiography, PCO) (ENDSTATION-1).

## The orchestration seam

The tomographic acquisition is the seam a CORA edge replaces. At ID19 it runs as a BLISS scan procedure: a continuous rotation of the sample stage coupled to the Lima detector frame capture, the sample spun through the beam while the detector records a projection at each angle. That rotation-coupled-to-capture loop is the orchestration CORA's edge conducts over the same floor, driving through the BLISS device layer rather than BLISS owning the loop, with the conduct-versus-drive-through split decided per routine (CTRL-2).

This is CORA's first imaging deployment on the BLISS floor, so the seam is the whole point. The technique is plain microtomography, the existing `tomography` Method (TECH-1) the 2-BM pilot and TomoWise carry; ID19 coins no new device family. What ID19 proves is that the `ControlPort` and the conducting seam are genuinely control-system-agnostic: the same edge that conducts a scan over EPICS / ophyd-async at Diamond conducts it over BLISS / Tango here, against Lima detector servers and BLISS axes instead of EPICS IOCs.

The downstream volume reconstruction is not a beamline device. Recovering the real-space volume from the recorded projection stack is `ComputePort` work, the same reconstruction leg the other imaging beamlines carry, run over the port rather than modelled as an endstation Asset.

### The seam: CORA and the floor

This is where CORA's design meets the ID19 floor. The shape matches the other imaging beamlines'; only the floor underneath is different.

CORA **owns** (its conducting engine, over the `ControlPort`):

- the tomographic acquisition: emitting the rotation trajectory over the rotation stage, coupling it to the Lima detector capture, and reading the projection frames through the series;
- the choice of technique and timing, gated by the [trust boundary](../governance.md#the-trust-boundary).

CORA **drives through** (the floor it actuates and observes, and does not replace):

- the **BLISS / Tango** device layer: the rotation and sample stages (BLISS axes over Elmo and IcePAP), the Lima area detectors (Tango device servers), the monochromator and shutters, the `ControlPort` boundary. This is the EPICS-to-BLISS substitution: same port, different floor (CTRL-1).
- the detector file-writing to the ESRF data store, where the Lima frames land. That is plumbing CORA observes; CORA moves the frames, over the `TransferPort`, into CORA's own Dataset of record, and records the Dataset rather than adopting the facility's data catalog.

So CORA brings one conducting engine to ID19, working over the ports: the tomographic scan over the `ControlPort` (here against BLISS, not EPICS), the volume reconstruction over the `ComputePort`, and data egress over the `TransferPort` into the CORA Dataset. The reconstruction is a clean `ComputePort` leg, not a beamline device (TECH-1).

The BLISS / Tango device servers (the Lima detector servers, the Elmo and IcePAP controllers) are referenced by interface only, never registered as Assets beyond the two `MotionController` handles.

## Equipment protection

The shutter handles are known from the config (`frontend`, `id19/bsh/1`, `id19/bsh/2`, all TangoShutters), but the PSS search-and-secure permit signals behind them are **not in the config** and are not invented here (PSS-1). The config is a device database, not a safety-system description. CORA names the shutters but not the permit signals until the beamline team supplies them.

The Enclosure permit shape for the two hutches and the hazard tier are carried pending at the ESRF Site; the governance and safety envelope follow the 2-BM shape (see [Governance](../governance.md)). The ESRF operator pool and review are pending at the Site (GOV-1), and Clearances are issued at the ESRF Site.

See [Open questions](../questions.md) for the control, detection, and safety items still to confirm, and [Model](../model.md#deliberately-not-here-yet) for the deferred endstations and why this BLISS-floor imaging deployment coins no new vocabulary.
