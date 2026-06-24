# Cautions

*Operator tribal knowledge, reverse-engineered from quirks visible in the FXI profile collection. Each is inferred from source, not confirmed by staff, so it is carried `confirm`.*

A Caution is a hazard or quirk an operator should know. These are read from comments, retry loops, and wiring oddities in `NSLS2/fxi-profile-collection`; the real operational impact needs staff confirmation.

## Zone-plate / Bertrand-lens Y axes are cross-wired

- Target: `ZonePlate`, `BetrandLens` (`startup/11-txm_motor.py`).
- What: `zp.y` is wired to the `{BLens:1-Ax:Y}` record and `betr.y` is wired to the `{ZP:1-Ax:Y}` record. The two Y axes are cross-wired in source, and several related axes are commented out.
- Why it matters: moving "the zone plate Y" actually drives the Bertrand-lens Y record and vice versa. The descriptor preserves this faithfully; do not "fix" it without confirming the real wiring with FXI staff.

## Flaky safety shutter (retry loop)

- Target: the PPS photon shutter (`nslsii.TwoButtonShutter`, re-vendored in `startup/11-txm_motor.py`).
- What: the shutter is wrapped with `RETRY_PERIOD = 1` and `MAX_ATTEMPTS = 10`; the code re-actuates it on failure.
- Why it matters: the shutter can need several actuation attempts. A scan that opens or closes it (every dark/flat cycle) should expect and tolerate the retry, not treat the first failure as fatal.

## Zebra register overflow

- Target: the Zebra position-capture box (`startup/18-zebra.py`).
- What: a `ZEBRA_OVERFLOW` constant marks where the position-capture register wraps.
- Why it matters: a fly scan whose accumulated position exceeds the register wraps the count; trigger generation past the overflow point is a known hazard the scan must stay within.

## Camera staging timeout

- Target: the Kinetix camera (`startup/10-area-detector.py`).
- What: staging raises if the camera is not in the Idle state ("Kinetix must be in the Idle state to stage").
- Why it matters: a scan that starts before the camera settles fails at staging; the Conductor must wait for Idle before arming.

## Buggy-IOC force-set

- Target: mirror bender / load-cell precision in source.
- What: a comment notes a force-set value "should be fixed at the IOC level".
- Why it matters: a value is being set in the profile collection to work around an IOC bug; if the IOC is fixed, the workaround should be removed. Carried as a watch-item.
