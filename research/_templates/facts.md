# Extracted facts: <beamline / source-repo>

Candidate device facts for `<beamline-id>` (facility `<facility>`). Candidates only; confirm every row before modeling. Source: `<the public config / instrument repo read, with commit or date>`. Every value is carried `confirm` until beamline staff verify it: a config snapshot or instrument repo is strong evidence, not a CORA-owned fact.

## Device inventory

Map each device onto a CORA Family at Asset granularity (the stage, not the per-axis tuning). Carry the real control handle (EPICS PV prefix, BLISS object name, Tango device URL) in the descriptor `pv` field, the opaque control-handle slot. A suggested family ending in `(?)` is a class-name fallback, not a confident map: resolve it against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV / axes (handle) | Enclosure | Stage | Labels | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| <name> | <Family or Family (?)> | <prefix; axis=`leaf`> | <hutch> | <source/optics/sample/detection> | <labels> | yes |

## Role hints

<Which devices present which Role (Detector / Positioner / Sensor / Controller / Regulator), where the source makes it inferable. Note any settable-continuous-setpoint actuators (Regulator candidates) and any flow / temperature controllers.>

## Trust hints

<Anything the controls source reveals about authorization: queueserver / user_group_permissions, access groups, p-group / ownerGroup chains. CORA models its own Trust spine, so this is input to the seam read, not a binding.>

## New-family watch

<Any device class that does not map to an existing catalog Family. Do NOT coin a Family here. Flag it as a candidate, name the discriminator (what it measures / does that no existing Family covers), and note how many other beamlines bind the same class (the rule-of-three trigger). Coining a Family from a single beamline, or from a class with no instantiated device, is invention.>

## Deferred / absent

<Devices that are in the science but absent from public source (a polychromator behind a skip=True flag, a firewalled detector backend). Name them as open questions (TAG-1) rather than modeling them. "Device X missing" is only a defect if X is in source and wrongly omitted.>
