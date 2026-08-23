"""BC-application-layer errors for the Supply BC.

These errors are raised by application handlers (not domain logic)
and mapped to HTTP / MCP responses by the BC's exception handlers in
`cora/supply/routes.py`.

Domain errors (raised by aggregates / deciders) live with their
aggregate, for example `aggregates/supply/state.py`.

Distinct class from each other BC's `UnauthorizedError`: each BC
owns its own application-error namespace so a Supply 403 is
distinguishable from other BCs' 403s in logs / aggregator filters
(documented in CONTRIBUTING.md "BC-application-layer errors").
"""


class UnauthorizedError(Exception):
    """The Authorize port denied the command."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class UnknownSupplyNameError(ValueError):
    """A caller named a Supply `supply_kind_from_name` does not recognize.

    `seed_observed_supplies` itself only warns and skips an unrecognized
    name (a defensive default for any future caller of this BC-level
    function), which is right for that function in isolation but wrong
    as the ONLY check for BLEPS_SUPPLY_CHANNELS specifically: an
    unrecognized `supply` there silently drops that channel from BOTH
    seeding and observation, leaving an equipment-protection channel
    permanently unmonitored with nothing more than one boot-time log
    line to show for it. The composition root (the one place allowed to
    depend on both `cora.infrastructure.config` and `cora.supply`) is
    expected to call `validate_supply_names` and let this propagate,
    matching the fail-loud posture
    `Settings._require_communications_fault_pv_with_bleps_channels`
    already takes for the sibling misconfiguration on the same list.
    """

    def __init__(self, unknown_names: frozenset[str]) -> None:
        super().__init__(
            f"{sorted(unknown_names)!r} named in BLEPS_SUPPLY_CHANNELS is not a "
            "recognized Supply name (see supply_kind_from_name's _KIND_BY_NAME "
            "table); add it there or fix the typo"
        )
        self.unknown_names = unknown_names
