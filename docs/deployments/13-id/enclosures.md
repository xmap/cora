# Enclosures

*Enclosure BC permits that gate Runs and Procedures at 13-ID.*

An Enclosure models the observed permit status of an access-gated volume: a physical space whose interlock and search-and-secure sequence must be satisfied before beam-on work proceeds inside it. See the [Enclosure module](../../architecture/modules/enclosure/index.md) for the aggregate shape, the permit and lifecycle axes, and the pre-flight gate that reads them.

13-ID has two Enclosures: the shared upstream optics zone `13-ID-optics` (the 13-ID-A first optics, common to the sector) and the high-pressure experiment hutch `13-ID-D`. The beamline id is `13-ID`; the station letter `D` names the experiment hutch, which is why the hutch is an Enclosure rather than part of the beamline name. At APS the sibling GSECARS letters (`13-ID-C`, `13-ID-E`) are separate co-located stations that share the sector front end, so `13-ID-D` identifies this beamline's hutch, not a sub-part of a `13-ID` whole. Each Enclosure is its own access-gated volume with its own Personnel Safety System permit, observed independently, and each is anchored to the APS Site via `facility_code = "aps"`.

<!-- beamline:enclosures -->
<!-- /beamline:enclosures -->

The Gates column derives from the beam-path groups that name each Enclosure; the permit signal is the search-and-secure PV CORA reads to observe the permit.

Each Device declares which Enclosure it sits in via `located_in_enclosure_id`. The shared optics band (the silicon double-crystal monochromator, the focusing mirrors, the beam-defining slits, the clean-up pinhole, and the attenuator) is in `13-ID-optics`; the diamond anvil cell, the DAC positioning stage and lift table, the metrology spectrometer, and the diffraction detection chain are in `13-ID-D`. The Located-in column on [Assets](inventory.md) is the per-Device source of truth.

## Permit signals and the laser-safety axis

Each Enclosure's permit maps off its Personnel Safety System search-and-secure PV shown as its `permit_signal` above: an Enclosure is Permitted when that PV reads its permitted value. CORA reads these read-only: it never drives, holds, or releases the permit or the beam, and the PSS retains sole interlock authority. The exact PSS permit leaves are absent from the reverse-engineered EPICS support tree and are carried pending staff confirmation (`ENC-1`, `PSS-1`).

The `13-ID-D` endstation carries a second permit axis the rest of the fleet has not needed: a dedicated laser-safety enclosure permit, gated by a Koyo DL205 safety PLC (`13IDD_laserPLC:`) governing whether the class-4 heating lasers may emit into the hutch. CORA models this as an Enclosure permit concern on the laser-emission axis, not as a device, carried pending and not invented (`LASER-1`). See [Governance](governance.md#the-laser-safety-permit-leaf).

`start_run` and `start_procedure` run an Enclosure pre-flight gate that derives the Enclosures in scope from the bound Assets and requires each to be Permitted. The chain walk, the error classes, and the HTTP codes are on the [module page](../../architecture/modules/enclosure/index.md#cross-module-boundaries). An optics-only Procedure gates on `13-ID-optics` alone, while a high-pressure diffraction Run spanning the optics and the endstation needs both Permitted.
