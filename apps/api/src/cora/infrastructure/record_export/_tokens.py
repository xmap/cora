"""The per-export UUID surrogate map.

Per `project_record_export_v3.md` F5: a TOKEN is a random surrogate,
never a hash. A hash is deterministic, so against a known candidate set
(a ten-person roster, a facility's proposal list) it is brute-forceable
in as many guesses as there are candidates -- the same defect as
publishing a signature beside a redacted payload. `TokenMap` mints a
fresh `uuid4()` per distinct source string the first time it is seen
and returns that same surrogate on every later lookup within the same
export, which is what preserves joins (both within tier 1 and across
the tier-1/tier-2 seam, per F5) without making the surrogate
derivable from its source.

The map itself is an artifact of the export, not the record: F5 says it
"never ships" and sits under the same retention obligation as the
unredacted record. `surrogate_by_source` exists so a caller can persist
it separately; nothing in this package ever feeds it back into anything
that gets hashed as "the published record".
"""

from uuid import uuid4


class TokenMap:
    """Mint-once, reuse-after per-export UUID surrogates. Never a hash."""

    def __init__(self) -> None:
        self._surrogates: dict[str, str] = {}

    def token_uuid(self, source: str | None) -> str | None:
        """Surrogate for `source`, or `None` if `source` is `None`.

        `None` is a legitimate value for an optional UUID column
        (`causation_id`, `principal_id`, ...) and must pass through
        as `None` rather than being tokenized or dropped.
        """
        if source is None:
            return None
        if source not in self._surrogates:
            self._surrogates[source] = str(uuid4())
        return self._surrogates[source]

    @property
    def surrogate_by_source(self) -> dict[str, str]:
        """Source UUID -> surrogate, for retention under H1's obligation.

        A copy, not a live view: callers must not be able to mutate the
        map this instance uses for tokenization by holding this dict.
        """
        return dict(self._surrogates)


__all__ = ["TokenMap"]
