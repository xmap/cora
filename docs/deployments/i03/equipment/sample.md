# Sample

*The I03 MX endstation. Design-phase; values are reverse-engineered from dodal or inferred.*

The sample stage is the experiment hutch: the goniometer that orients the crystal, the sample-centring base, the automated sample-changing robot, and the sample environment. It is the modelling heart of I03 and the source of its one catalog change.

## The goniometer (the graduated Family)

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `Goniometer` | [`Goniometer`](../../../catalog/families.md) | `BL03I-MO-SGON-01:` | the Smargon micro-goniometer: omega / chi / phi rotation + x / y / z sample-centring, with centre-of-rotation control and an unrestricted (wrapped) omega |
| `LowerGonio` | `LinearStage` | `BL03I-MO-GONP-01:` | the lower goniometer x / y / z base |

The Smargon is the reason I03 **graduates the Goniometer Family** from pending to defined. The catalog had documented `Goniometer` as a pending kind; the Smargon is CORA's first canonical instance, so it earns the Family. `Goniometer` stays a bare role-noun: distinct from `RotaryStage` (a single tomographic rotation axis that carries PSO fly-scan Following, which the goniometer does not) and from `TiltStage` (a limited-range tilt with no primary rotation axis). chi-vs-kappa and axis count are per-Asset settings, not Family splits. The per-axis decomposition (omega / chi / phi as rotation Assets, x / y / z as translation Assets under the Goniometer Assembly) and the centre-of-rotation calibration are carried pending (GONIO-1). The six real dodal motors are the controls-layer realization of the chi / x coupling and are not modelled as separate spine Assets.

## The autonomous sample-changing robot

| Device | Presents | Control handle | Notes |
| --- | --- | --- | --- |
| `Robot` | Positioner Role | `BL03I-MO-ROBOT-01:` | an automated sample-changing robot (BartRobot) |

This is the device that makes MX automation interesting, and the one an adversarial review kept CORA from over-modelling. The robot is **not** a new `SampleChanger` Family: following the settled 19-BM (ROBOT-1) and 32-ID positions, it is **one Positioner-presenting Asset** that loads and unloads a `Subject` (a pin / puck from a dewar queue), gated by a Clearance that must be Active (issued after a safety review), with the vendor robot in a bound Model. The genuinely new and non-obvious parts, the sample-queue custody lifecycle (Received to mounted-on-goniometer to measured to Returned / Stored) and the autonomous load gate, are `Subject` and Clearance modelling, not an equipment Family. The exchange workflow is a Procedure over the spine, deferred until the design and review land (ROBOT-1).

## The sample environment

| Device | Family | Control handle | Notes |
| --- | --- | --- | --- |
| `Backlight` | `Backlight` (loose) | `BL03I` | sample illumination for on-axis viewing |
| `Cryostream` | `TemperatureController` (loose) | `BL03I-EA-CSTRM-01:` | Oxford cryostream cold-gas cooling; a settable actuator |
| `Thawer` | `TemperatureController` (loose) | `BL03I-EA-THAW-01` | sample thawing; a settable actuator |

The cryostream and thawer reuse I22's loose `TemperatureController` family; whether CORA commands their setpoints (versus reading them back) is the same open settable-actuator question as 7-BM FLOW-1 and I22 ENV-1 (ENV-1). The backlight is the one genuinely new loose family I03 introduces: no existing Family carries an illumination affordance, so it is carried loose and earned only on a rule-of-three (DET-1).

Whether the goniometer + aperture-scatterguard + backlight + cryostream compose an MX-endstation Assembly (the analogue of 2-BM's SampleTower) is deferred: grouping is promoted only when a feature must act on the whole (ASSEMBLY-1).

See [Open questions](../questions.md) for the confirmations still needed and [Inventory](../inventory.md) for the Asset tree.
