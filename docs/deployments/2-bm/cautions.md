# Cautions

*Caution BC Cautions targeting 2-BM Assets and Procedures.*

Operator tribal knowledge captured at shakedown, first-light, or production time. Surfaced on every future Run start via the `CautionLookup` snapshot. See [Model](../../architecture/model.md) for the aggregate shape.

| Target | Category | Severity | Text |
| --- | --- | --- | --- |
| `Rotary` | `Wear` | `Caution` | Misses index pulse on cold-start home; retry after 5s |
| `HexapodDrive` | `Wear` | `Caution` | Locks up under sustained load or over-travel; recover via `hexapod_reboot` |
| `Hexapod` | `Wear` | `Caution` | Y dial misreads after reboot; set Y dial to 350 before any Y move |

## Aerotech cold-start index miss

`Wear` / `Caution`. Tags: `aerotech`, `home`, `cold_start`.

**Observation.** The Aerotech ABRS rotary stage misses its index pulse on the first home attempt after a power cycle. Subsequent homes work; only the cold-start first attempt is affected. Observed during 2-BM shakedown on 2026-05-17.

**Workaround.** Issue `HOME` command, wait 5s for settling, re-issue `HOME`. Verify `index_pulse=1` on encoder readback before treating home as successful. Optionally pre-warm the stage by jogging +/-1° before the first home.

**Lifetime.** No `expires_at` (permanent until superseded or retired). Persists on the operator banner for every future Run start at 2-BM until the underlying stage is replaced or recalibrated.

## Hexapod controller lockup

`Wear` / `Caution`. Tags: `hexapod`, `controller_lockup`, `pdu_power_cycle`, `ioc_restart`.

**Observation.** The Aerotech HexGen hexapod controller (driving the Aerotech HEX300-230HL hexapod stage per the [2-BM beamline components page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html)) occasionally locks up under sustained load: the `2bmHXP:HexapodAllEnabled` EPICS PV reads `0` while motion commands return no error. Operator-observable symptom is the hexapod stops responding to position requests even though no fault has been raised by the motion-control layer. A second, distinct trigger for the same recovery is documented on the staff [sample motor stack page](https://docs2bm.readthedocs.io/en/latest/source/ops/item_050.html) (`item_050`): driving the hexapod past its travel range raises a controller drive error that disconnects all axis drivers and turns the normally-green Enable/Fault indicator off. Both failure modes clear with the same `hexapod_reboot` ceremony.

**Workaround.** Run `hexapod_reboot.py` (in [`decarlof/2bmb-bin`](https://github.com/decarlof/2bmb-bin)): stops the hexapod IOC, power-cycles PDU outlet 5 (the operator-facing outlet number; the NetBooter relay index is zero-based, so the wire call is `rly=4`) with the script's power-settling delays (10 s off, 30 s on), restarts the IOC, polls `HexapodAllEnabled` for up to 180s. If the PV is still `0` after the timeout, `caput 2bmHXP:EnableWork.PROC 1` to force-enable, then re-poll. Manual checks during recovery: verify outlet state via NetBooter `/status.xml`; SSH `2bmb@arcturus` for IOC log inspection.

**Modeling note.** This Caution targets `HexapodDrive` (the controller Asset) rather than `Hexapod` (the stage), because the failure mode is in the drive electronics and the workaround is entirely controller-side (PDU outlet, IOC restart, EPICS PV poll). The [2-BM beamline components page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html) calls the EPICS interface "native Aerotech Ensemble" but does not name the controller box, so the Asset records what is known (Aerotech vendor, drives the hexapod) and leaves identity details to settings placeholders confirmed via `update_asset_settings`. The separate [Y-stage dial-misreset Caution](#hexapod-y-stage-dial-misreset-after-reboot) below targets the stage instead, because that quirk is a homing / encoder-dial artifact, not a drive-electronics fault.

**Lifetime.** No `expires_at` (permanent until superseded or retired). Surfaces on every future Run start at 2-BM that targets `HexapodDrive` (or, by `controller_id` back-reference traversal, `Hexapod`), so operators know to run the recovery routine on first sign of unresponsiveness rather than chasing a phantom motion-control bug.

## Hexapod Y-stage dial misreset after reboot

`Wear` / `Caution`. Tags: `hexapod`, `y_axis`, `post_reboot`, `dial_reset`.

**Observation.** After the hexapod controller is rebooted (the lockup recovery above, or any power-cycle), every axis homes correctly except Y. The Y dial position resets to 0 while the encoder readback dial reads 350, so the two disagree; commanding a Y move in this state raises a drive error. Documented on the staff [sample motor stack page](https://docs2bm.readthedocs.io/en/latest/source/ops/item_050.html) (`item_050`).

**Workaround.** Before commanding any Y motion after a reboot, manually set the Y dial to 350 so it agrees with the encoder readback, then resume normal operation. This is a required post-reboot step, not an optional one: skipping it turns the first Y move into a drive error that forces another reboot.

**Modeling note.** Targets `Hexapod` (the stage) rather than `HexapodDrive` (the controller), because the quirk is a stage homing / encoder-dial artifact, not a drive-electronics fault. It is deliberately left at the hexapod level rather than narrowed to the `Hexapod_Y` degree-of-freedom facet so that it surfaces on any hexapod-level Run, including the reboot Procedure itself (which targets `Hexapod`); narrowing to `Hexapod_Y` waits on confirming that `CautionLookup` traverses `parent_id` the way it traverses `controller_id`.

**Lifetime.** No `expires_at` (permanent until superseded or retired). Surfaces on every future Run start at 2-BM that touches the hexapod, so an operator who has just rebooted is reminded to fix the Y dial before the first Y move. That this quirk is still current is tracked as `HXP-8`.

## Pending

| Target | Category | Severity | Text |
| --- | --- | --- | --- |
| 2-BM Unit | | | Vibration threshold exceeded after air-handler shutdown |
| `Camera` | | | Detector dark-frame drift after long beam-off periods |
| `Scintillator` | | | Scintillator browning under prolonged white-beam exposure |
| Sample-stage Devices | | | Sample-stage backlash after manual handling |
| `Monochromator` | | | Flat-field stripe pattern drifts over hours (DMM optics); acquire flats as close to scan time as possible |
