# Enclosures

*Enclosure BC permits that gate Runs and Procedures at 12-ID.*

An Enclosure models the observed permit status of an access-gated volume: a physical space whose interlock and search-and-secure sequence must be satisfied before beam-on work proceeds inside it. See the [Enclosure module](../../architecture/modules/enclosure/index.md) for the aggregate shape, the permit and lifecycle axes, and the pre-flight gate that reads them.

12-ID has two Enclosures: the shared upstream optics zone `12-ID-optics` and the USAXS experiment hutch `12-ID-E`. The beamline id is `12-ID`; the station letter `E` names the experiment hutch, which is why the hutch is an Enclosure rather than part of the beamline name. At APS the sibling letters (`12-ID-B`, `12-ID-C`) are separate co-located beamlines that share the sector front end, so `12-ID-E` identifies this beamline's hutch, not a sub-part of a `12-ID` whole. Each Enclosure is its own access-gated volume with its own Personnel Safety System permit, observed independently, and each is anchored to the APS Site via `facility_code = "aps"`.

<!-- beamline:enclosures -->
<!-- /beamline:enclosures -->

The Gates column derives from the beam-path groups that name each Enclosure; the permit signal is the search-and-secure PV CORA reads to observe the permit.

Each Device declares which Enclosure it sits in via `located_in_enclosure_id`. The shared optics band (the double-crystal monochromator, the attenuator filter bank, and the guard and USAXS slits) is in `12-ID-optics`; the Bonse-Hart collimator and analyzer crystal stages, the sample stages and environment, the UPD photodiode and flux monitors, and the SAXS and WAXS area detectors are in `12-ID-E`. The Located-in column on [Assets](inventory.md) is the per-Device source of truth.

## Permit signal and gate

Each Enclosure's permit maps off its Personnel Safety System search-and-secure PV shown as its `permit_signal` above: an Enclosure is Permitted when that PV reads its permitted value. CORA reads these read-only: it never drives, holds, or releases the permit or the beam, and the PSS retains sole interlock authority. The exact PSS permit leaves are absent from the reverse-engineered instrument config and are carried pending staff confirmation (`ENC-1`, `PSS-1`).

`start_run` and `start_procedure` run an Enclosure pre-flight gate that derives the Enclosures in scope from the bound Assets and requires each to be Permitted. The chain walk, the error classes, and the HTTP codes are on the [module page](../../architecture/modules/enclosure/index.md#cross-module-boundaries). An optics-only Procedure gates on `12-ID-optics` alone, while a USAXS Run spanning the optics and the endstation needs both Permitted.
