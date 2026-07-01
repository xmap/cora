# Open questions

*What CORA needs the ID32 team to confirm before the model can be trusted.*

ID32 was reverse-engineered from the ESRF's open BLISS Beacon device database ([gitlab.esrf.fr/id32/beamline_configuration](https://gitlab.esrf.fr/id32/beamline_configuration), a git mirror of the live Beacon config), so the control handles in the [Inventory](inventory.md) are the beamline's real Tango / IcePAP / BLISS addresses, read from the config rather than confirmed by staff. This is CORA's first ESRF Site and first BLISS / Tango / IcePAP controls house-style. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: a shared optics zone feeding the RIXS and XMCD endstations, or a different layout? | A shared `id32-optics` zone and the `id32-rixs` and `id32-xmcd` experiment hutches. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The APPLE-II undulator period and segment count. | An APPLE-II undulator source on the `id/master/id32` device server; period pending. | The source Asset detail. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The ESRF-EBS storage-ring state ID32 reads. | Observe-only machine state, a loose `StorageRing`; exact handles pending. | The machine-state observation. |
| POL-1 | Blocks-go-live | The polarization value domain (linear / circular) and the phase conversion: pin it as a Calibration or run it rule-less on the live controller? | A `PseudoAxis` over the APPLE-II phase; rule-less by default (the i06 / i10 precedent). | The polarization-axis modelling. |
| MONO-1 | Blocks-go-live | The PGM grating line densities, the cff, the incident-energy range, and the exact handles. | A soft X-ray PGM bound to `GratingMonochromator`; energy a `PseudoAxis`. | The monochromator and incident-energy Assets. |
| OPT-1 | Nice-to-have | The focusing-mirror coatings and the exact handles. | Soft X-ray focusing mirrors bound to `Mirror`. | The mirror Asset detail. |
| OPT-2 | Nice-to-have | The beam-defining slit blade-axis map and handles. | Slits bound to `Slit`. | The slit Asset detail. |

## RIXS endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-go-live | The 4-circle diffractometer (BLISS `DiffE4CH`, E4CH) circle roles and axes. | A `Goniometer`; the `Assembly(Diffractometer)` is named, not built. | The diffractometer geometry; the CORA structural modelling is on [Model](model.md#deliberately-not-here-yet). |
| DIFF-2 | Nice-to-have | The reciprocal-space (hkl) coordination over the diffractometer. | A reciprocal-space `PseudoAxis`, the rule deferred. | The reciprocal-space Asset. |
| RIXS-1 | Blocks-go-live | The RIXS and XES dispersive spectrometer arms (the `SpectrometerArmsController` geometry, the Rowland radii, the grating modes). | Both bind the catalog `SpectrometerArm` Family (graduated across SIX + ID32 RIXS/XES + ID28); the per-Asset arm geometry stays pending. | The spectrometer-arm geometry; the family graduation is settled (see [Model](model.md#loose-families-held-at-the-rule-of-three)). |
| POL-2 | Nice-to-have | The RIXS scattered-beam polarimeter (the `thpol` / `chipol` / `tthpol` block). | Binds the catalog `PolarizationAnalyzer`, graduated across 4-ID / i10 / ID32 / P09. | The polarimeter modelling. |
| DET-1 | Blocks-go-live | The Andor CCD configurations (RIXS `andor_1`, XES `andor_2`). | Both bind `Camera`. | The detector modelling. |

## XMCD endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MAG-1 | Blocks-go-live | The 9 T / 4 T XMCD split-coil magnet (field range, ramp, the two coils) and its cryogen plant. | Binds the catalog `Magnet` Family (graduated across 4-ID + i10-1 + ID32); the field is a settable axis (Regulator), the per-Asset field detail pending. | The per-Asset magnet field / control detail; the family graduation is settled (see [Model](model.md#loose-families-held-at-the-rule-of-three)). |
| TEMP-1 | Nice-to-have | The LakeShore 336 (VTI sample) and 340 (coil / shield diagnostics) sensor and loop maps, and the He needle valve. | Two `TemperatureController` Assets presenting the `Regulator` Role; the needle valve folds into the VTI. | The temperature-control modelling. |
| SAMPLE-1 | Blocks-go-live | The XMCD sample-positioning stage axes inside the magnet bore. | A `LinearStage`; axis set pending. | The sample-stage modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the Tango / IcePAP / BLISS handles read from the public Beacon config current and correct? | The handles in the descriptor are taken from the BLISS config and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The ESRF personnel-safety permit signals and the photon / front-end shutters (absent from the BLISS config). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the liquid-helium supply for the magnet. | Photon beam, cooling water, vacuum, and liquid helium. | The Supply observations. |
| GOV-1 | Nice-to-have | The ESRF operator pool and safety-review structure (site-level). | Carried pending on the ESRF Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Do RIXS, XMCD, and XES enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the SIX RIXS, the 4-ID / i06 / i10 XMCD, and the xas_spectroscopy XES slugs; none coined. | The technique Capabilities. |
