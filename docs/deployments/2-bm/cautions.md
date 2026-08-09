# Cautions

*Caution BC Cautions in force at 2-BM: the operator advisories surfaced before a Run.*

A caution is operator tribal knowledge about an Asset, an observed quirk paired with a workaround, captured at shakedown, first light, or in production. It shows at the start of any Run whose scope includes its target. That scope is the Assets the Run's Plan binds, widened at Run start to add each bound Asset's controller and the Assets that contain it; a caution filed on a controller or on a containing unit therefore reaches a Run that binds only the stage beneath it. Cautions warn, they never block: blocking authority belongs to the [Safety](../../architecture/modules/safety/index.md) BC. None of the cautions below sets an expiry; each persists until an operator supersedes or retires it. See [Model](../../architecture/model.md) for the aggregate shape.

2-BM has one rotary-stage quirk and one hexapod-controller quirk, plus a queue of cautions still to be written up.

## Rotary stage: cold-start index miss

`Wear` / `Caution`, filed against `Rotary`. Tags: `aerotech`, `home`, `cold_start`.

The Aerotech ABRS rotary stage misses its index pulse on the first home attempt after a power cycle. Later homes succeed; only the cold-start first attempt is affected.

**Workaround.** Issue `HOME`, wait about five seconds for the stage to settle, then issue `HOME` again, and confirm the encoder reads `index_pulse=1` before treating the home as good. Pre-warming the stage with a small jog before the first home also avoids it.

## Hexapod: controller lockup

`Wear` / `Caution`, filed against `HexapodDrive`. The fault is in the drive electronics and the recovery is entirely controller-side, so the caution sits on the drive controller rather than the stage. Tags: `hexapod`, `controller_lockup`, `pdu_power_cycle`, `ioc_restart`.

The hexapod controller occasionally stops responding while reporting no fault: it no longer moves to commanded positions and the `2bmHXP:HexapodAllEnabled` signal reads `0`. Driving the hexapod past its travel range reaches the same state by another route, disconnecting the axis drivers and turning the Enable indicator off. Both clear the same way. Staff confirmed the over-travel route as current on 2026-07-28 (HXP-8); it is also documented on the [sample motor stack page](https://docs2bm.readthedocs.io/en/latest/source/ops/item_050.html).

**Workaround.** Recover with the [`hexapod_reboot` recipe](recipes.md#hexapod_reboot): it stops the IOC, power-cycles the controller, restarts the IOC, and waits for every axis to re-enable, with a force-enable and re-poll if the enable signal is still `0` after the wait. The recipe holds the outlet, timing, and PV details. Treat an unresponsive hexapod as this lockup rather than chasing a motion-control bug.

A reboot needs no manual Y-dial correction: staff confirmed on 2026-07-28 that the axes come back homed, and the dial-to-user convention is recorded as [calibration state](inventory.md#hexapod-dof-model) rather than as an advisory. The sample motor stack page still instructs the operator to set the Y dial by hand, pending a staff-side edit. That instruction is out of date, and it is not a caution to add back here.
