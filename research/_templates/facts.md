# Extracted facts: <beamline / source-repo>

Candidate device facts for `<beamline-id>` (facility `<facility>`). Candidates only; confirm every row before modeling. Source: `<the public config / instrument repo read, with commit or date>`. Every value is carried `confirm` until beamline staff verify it: a config snapshot or instrument repo is strong evidence, not a CORA-owned fact.

## Device inventory

Map each device onto a CORA Family at **Asset granularity**: one row per stage / assembly (a Monochromator, a Mirror, an IonChambers electrometer), NOT one row per motor axis. This is what a deployment descriptor binds: one device, one `family`, one `pv` prefix. The per-axis handles are real and worth recording, but they belong as sub-detail under the Asset, not as separate devices (the failure mode is a 7-row DCM where the descriptor wants one). Carry the real control handle (EPICS PV prefix, BLISS object name, Tango device URL) in the `pv` slot. A suggested family ending in `(?)` is a class-name fallback, not a confident map: resolve it against `catalog/catalog.yaml` before binding.

The Asset row carries the device-level **PV prefix** (what the descriptor binds). Its component axes go in the **Axes** column as `name=`leaf`` pairs, read verbatim from source: this is the provenance that later justifies a Capability / Method mapping (e.g. a DCM with bragg+para+perp+energy is an energy-scanning mono, not a fixed crystal). Every handle must be a complete string read from source; if you cannot read the full handle, leave it blank and say so in confirm, never a fragment.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| <Asset name> | <Family or Family (?)> | <device prefix> | <axis=`leaf`; axis=`leaf`; ...> | <hutch> | <source/optics/sample/detection/diagnostics> | yes |

## Role hints

<Which devices present which Role (Detector / Positioner / Sensor / Controller / Regulator), where the source makes it inferable. Note any settable-continuous-setpoint actuators (Regulator candidates) and any flow / temperature controllers.>

## Trust hints

<Anything the controls source reveals about authorization: queueserver / user_group_permissions, access groups, p-group / ownerGroup chains. CORA models its own Trust spine, so this is input to the seam read, not a binding.>

## New-family watch

<Any device class that does not map to an existing catalog Family. Do NOT coin a Family here. Flag it as a candidate, name the discriminator (what it measures / does that no existing Family covers), and note how many other beamlines bind the same class (the rule-of-three trigger). Coining a Family from a single beamline, or from a class with no instantiated device, is invention.>

## Deferred / absent

<Devices that are in the science but absent from public source (a polychromator behind a skip=True flag, a firewalled detector backend). Name them as open questions (TAG-1) rather than modeling them. "Device X missing" is only a defect if X is in source and wrongly omitted.>
