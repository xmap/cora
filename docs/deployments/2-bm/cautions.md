# Cautions

*Caution BC Cautions in force at 2-BM: the operator advisories surfaced before a Run.*

A caution is operator tribal knowledge about an Asset, an observed quirk paired with a workaround, captured at shakedown, first light, or in production. It shows at the start of any Run whose scope includes its target. That scope is the Assets the Run's Plan binds, widened at Run start to add each bound Asset's controller and the Assets that contain it; a caution filed on a controller or on a containing unit therefore reaches a Run that binds only the stage beneath it. Cautions warn, they never block: blocking authority belongs to the [Safety](../../architecture/modules/safety/index.md) BC. None of the cautions below sets an expiry; each persists until an operator supersedes or retires it. See [Model](../../architecture/model.md) for the aggregate shape.

2-BM has one rotary-stage quirk and a linked pair of hexapod quirks, plus a queue of cautions still to be written up.

## Rotary stage: cold-start index miss

`Wear` / `Caution`, filed against `Rotary`. Tags: `aerotech`, `home`, `cold_start`.

The Aerotech ABRS rotary stage misses its index pulse on the first home attempt after a power cycle. Later homes succeed; only the cold-start first attempt is affected.

**Workaround.** Issue `HOME`, wait about five seconds for the stage to settle, then issue `HOME` again, and confirm the encoder reads `index_pulse=1` before treating the home as good. Pre-warming the stage with a small jog before the first home also avoids it.

## Hexapod: controller lockup and the Y dial after a reboot

These two travel together. The controller lockup is cleared by a reboot, and the reboot leaves the Y dial needing a manual reset before the next move, so an operator who meets the first will meet the second. Both are documented by 2-BM staff on the [sample motor stack page](https://docs2bm.readthedocs.io/en/latest/source/ops/item_050.html).

### Controller lockup

`Wear` / `Caution`, filed against `HexapodDrive`. The fault is in the drive electronics and the recovery is entirely controller-side, so the caution sits on the drive controller rather than the stage. Tags: `hexapod`, `controller_lockup`, `pdu_power_cycle`, `ioc_restart`.

The hexapod controller occasionally stops responding while reporting no fault: it no longer moves to commanded positions and the `2bmHXP:HexapodAllEnabled` signal reads `0`. Driving the hexapod past its travel range reaches the same state by another route, disconnecting the axis drivers and turning the Enable indicator off. Both clear the same way.

**Workaround.** Recover with the [`hexapod_reboot` recipe](recipes.md#hexapod_reboot): it stops the IOC, power-cycles the controller, restarts the IOC, and waits for every axis to re-enable, with a force-enable and re-poll if the enable signal is still `0` after the wait. The recipe holds the outlet, timing, and PV details. Treat an unresponsive hexapod as this lockup rather than chasing a motion-control bug.

### Y dial after a reboot

`Wear` / `Caution`, filed against `Hexapod`. This is a homing artifact of the stage, not a drive fault, so the caution sits on the stage. Tags: `hexapod`, `y_axis`, `post_reboot`, `dial_reset`.

After any hexapod reboot, every axis homes correctly except Y: the Y dial resets to 0 while the encoder reads 350, and the first Y move in that state faults. Set the Y dial to 350 so it agrees with the encoder before commanding any Y motion. This is a required post-reboot step, not an optional one: skipping it faults the move and forces another reboot.

## Pending

Cautions seen in the field but not yet written up:

| Target | Text |
| --- | --- |
| `2-BM` | Vibration threshold exceeded after air-handler shutdown |
| `Camera` | Detector dark-frame drift after long beam-off periods |
| `Scintillator` | Scintillator browning under prolonged white-beam exposure |
| `SampleTop_X` | Sample-stage backlash after manual handling |
| `Monochromator` | Flat-field stripe pattern drifts over hours (DMM optics) |
