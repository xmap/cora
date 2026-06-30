# Open questions

*What CORA needs the ID28 team to confirm before the model can be trusted.*

ID28 was reverse-engineered from the ESRF's open BLISS Beacon device database ([gitlab.esrf.fr/id28/beamline_configuration](https://gitlab.esrf.fr/id28/beamline_configuration), a git mirror of the live config), so the control handles in the [Inventory](inventory.md) are the beamline's real BLISS / Tango / IcePAP addresses, read from the config rather than confirmed by staff (the ID32 house-style precedent). Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: an optics zone (oh1 / oh2 / oh3) feeding the eh1 spectrometer endstation, or a different layout? | A shared `id28-optics` zone and the `id28-eh1` experiment hutch. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The period and segment count of the two in-vacuum undulators (`u22gap` IVU22a, `u133gap` IVU13-3c). | Two in-vacuum undulators on the ESRF_Undulator device server; the names imply 22 mm and 13 mm periods, segment detail pending. | The source Asset detail. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The ESRF-EBS storage-ring state ID28 reads. | Observe-only machine state, a loose `StorageRing`; exact handles pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The backscattering crystal / reflection, the meV energy resolution, the energy-scan partition rule, and the premono (OH1) / postmono (OH2) roles ahead of the main mono (OH3). | A `Monochromator` on the PI E518 piezo (`pimth` / `pimchi`); the meV energy is scanned by the ASL F700 crystal-temperature axis (`monot` / `deltae`), not a Bragg angle; energy is a `PseudoAxis` over the F700. | The monochromator and incident-energy Assets. |
| OPT-1 | Nice-to-have | The HFM / VFM mirror coatings and bender mechanics. | Two-bender focusing mirrors bound to `Mirror`. | The mirror Asset detail. |
| OPT-2 | Nice-to-have | The blade-axis map of the primary, mono, and sample slits. | Beam-defining `Slit` Assets (BLISS `slits_ph` / `slits_pv` / `slits_mx` / `slits_sh` / `slits_sv`); each with horizontal / vertical gap and offset. | The slit Asset detail. |
| DIAG-1 | Nice-to-have | The oh2 Elettra beam-position monitor: position-measuring (the loose `BeamPositionMonitor`) or a flux monitor? | The loose `BeamPositionMonitor` (already held under review). | The diagnostics Family. |

## The IXS spectrometer endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| RIXS-1 | Blocks-go-live | The multi-analyzer spectrometer arm (the `TwoThetaMultilayer` two-theta arm carrying the inclined analyzer crystals), and whether the loose `SpectrometerArm` Family is the right home at its further sighting. | The arm binds the loose `SpectrometerArm`, a further consumer after SIX + ID32; held, the graduation deferred to a dedicated PR. | The spectrometer-arm modelling; the CORA graduation decision is on [Model](model.md#a-further-spectrometerarm-consumer-held). |
| IXS-1 | Blocks-go-live | The analyzer-crystal array: the config shows analyzer slits a1..a9 and inclined-analyzer (`inca`) controllers for a2 / a3 / a4 (each with chi / th); how many crystals are populated, and whether they are one arm Asset or identity-bearing child Assets. | One `SpectrometerArm` Asset carrying the crystal array as a per-Asset setting, not child Assets. | The analyzer-array modelling; the CORA structural choice is on [Model](model.md#deliberately-not-here-yet). |
| SAMPLE-1 | Blocks-go-live | The IXS sample-positioning stage axes: which of the scattering-geometry axes (`sax` / `say` / `saz`, `th` / `sphi` / `chi`), the eh1_ss `iceid285` (`phi` / `omega` / `sz`), and the SmarAct fine stage make up the modelled stage. | A `LinearStage`; axis set pending. | The sample-stage modelling. |
| TEMP-1 | Nice-to-have | The sample-temperature environments (the 10 K displex LakeShore 340, the Oxford 700 cryostream, the nanodac gas blower) and which is the default. | `TemperatureController` Assets presenting the `Regulator` Role. | The temperature-control modelling. |
| DET-1 | Blocks-go-live | The per-analyzer IXS photon detectors and the Basler / PCO imaging cameras: how the `deta1..deta9` P201 counters and the `izero` / `ione` monitors map to the analyzer crystals. | The Basler and PCO bind `Camera`; the per-analyzer `deta1..deta9` counters and the `izero` / `ione` beam monitors are read from the config, the crystal map pending. | The detector modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the BLISS / Tango / IcePAP handles read from the public Beacon config current and correct? | The handles in the descriptor are taken from the BLISS config and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The ESRF personnel-safety permit signals behind the shutters. The config exposes the front-end shutter (`fe`) and the vacuum beam shutters (`bsh1` / `bsh2` / `bsh3` on `id28/v-bsh/0..2`), but not the PSS permit leaves. | The shutters are modelled (`FrontEndShutter`, the `bsh*` leaves carried on the enclosures); the permit signals behind them are to be named, not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the displex cryostat cryogen supply. | Photon beam, cooling water, and vacuum on the optics and flight path. | The Supply observations. |
| GOV-1 | Nice-to-have | The ESRF operator pool and safety-review structure (site-level). | Carried pending on the ESRF Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Does momentum-resolved IXS enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice reusing the `inelastic_x_ray_scattering` Method NSLS-II IXS left pending, the second consumer; none coined. | The IXS Capability. |
