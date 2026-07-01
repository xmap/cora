# Sample

*The MX experiment endstation: the goniometer, the cryostream, the backlight, and the beamstop. First cut.*

The MANACA experiment endstation (`manaca-experiment`) is where the crystal is held and oriented in the beam for rotation MX. It is a reverse-engineered first cut from Sirius's public facility pages; the goniometer geometry and handles are not published, carried `confirm` (`GONIO-1`).

## The endstation

- **`Goniometer`** (`Goniometer`): the goniometer that holds the crystal and rotates it through an oscillation, with sample centring and alignment. MANACA supports serial and room-temperature MX in addition to standard cryocooled collection. Reuses the graduated `Goniometer` family (the i03 MX precedent, exercised at FMX / AMX / MX3); axis set pending (`GONIO-1`).
- **`SampleTemperature`** (`TemperatureController`): the cryostream sample cooling; reuses the graduated `TemperatureController` family; handles pending (`TEMP-1`).
- **`Backlight`** (`Backlight`): the on-axis backlight / frontlight for viewing and centring; binds the catalog `Backlight` Family (graduated across the MX / imaging fleet, `DET-1`).
- **`BeamStop`** (`BeamStop`): the beamstop blocking the direct beam at the sample; axis set pending (`SAMPLE-1`).

These reuse the MX Families the fleet already carries (i03 / FMX / AMX / MX3): a goniometer, a cryostream temperature controller, a sample backlight, and a beamstop. MANACA coins no new Family.

## The sample changer

MANACA carries an automated 48-pin sample changer for high-throughput collection. Following the established MX robot precedent (i03 / i24 / MX3 `ROBOT-1`), it is modelled as a deferred sample-exchange Procedure over the spine, with a Subject custody thread tracking each crystal, rather than as a device family. The load / centre / collect / unmount loop is named on [Techniques](../techniques.md) and carried pending (`ROBOT-1`).

## Not modelled yet

The exact goniometer axes and geometry, the cryostream sensor and setpoint handles, the beamstop axes, and the serial / room-temperature sample-delivery detail are not published and are carried pending (`GONIO-1`, `TEMP-1`, `SAMPLE-1`). They land when LNLS staff confirm the endstation configuration. The [i03 sample](../../i03/equipment/sample.md) page shows the shape a fully-modelled MX endstation carries.
