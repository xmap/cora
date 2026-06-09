"""Aggregates owned by the Enclosure BC.

One aggregate: `Enclosure` (operator-controlled access volume whose
permit-to-enter state is observed from external interlock chains;
multiple instances at runtime, one per controlled area: hutch, cave,
sample-prep room, laser room). Permit observation lives on a single
operational axis (Permitted | NotPermitted | Unknown) per the D6.L2
observation-axis-only anti-lock; structural lifecycle (Active ->
Decommissioned) is the separate terminal axis per the Facility
two-axis precedent.
"""
