"""Pin `AssetLookupResult` free of walk-axis fields (chain-walk Anti-hook 5).

`AssetLookupResult` is a snapshot row: one-hop read fields are welcome
(name, tier, lifecycle, family_affordances, and future controller_id /
fixture_id / facility_code snapshots). A WALK-AXIS field -- one whose
purpose is to TRAVERSE a chain, notably `parent_id` -- must NOT live on
this row. Parent-chain traversal is `ancestors_of`'s job: it reads
`parent_id` internally and returns these same snapshot rows, never
exposing the traversal axis as a result field. Re-adding `parent_id`
(or `fixture_id`/`subject_id` used as a walk axis) to the snapshot row
would re-open the door to handler-side chain walks (the H1 anti-pattern
the H3 pick rejected).

5a: the dataclass fields must be disjoint from the walk-axis set.
5b: the docstring must carry the canonical phrase, so a future edit
    cannot silently re-invite a walk-axis field by rationale.
"""

import dataclasses

import pytest

from cora.infrastructure.ports.asset_lookup import AssetLookupResult

# Fields whose purpose is to traverse a chain. They belong behind walk
# methods (ancestors_of / descendants_of), never on the snapshot row.
_WALK_AXIS_FIELDS: frozenset[str] = frozenset({"parent_id", "fixture_id", "subject_id"})

_CANONICAL_PHRASE = "walk-axis fields go behind walk methods"


@pytest.mark.architecture
def test_asset_lookup_result_has_no_walk_axis_fields() -> None:
    field_names = {f.name for f in dataclasses.fields(AssetLookupResult)}
    leaked = field_names & _WALK_AXIS_FIELDS
    assert not leaked, (
        f"AssetLookupResult carries walk-axis field(s) {sorted(leaked)}. A field "
        "whose purpose is to traverse a chain belongs behind a walk method "
        "(ancestors_of), not on the snapshot row. See chain-walk Anti-hook 5."
    )


@pytest.mark.architecture
def test_asset_lookup_result_docstring_states_the_walk_axis_rule() -> None:
    doc = AssetLookupResult.__doc__ or ""
    assert _CANONICAL_PHRASE.lower() in doc.lower(), (
        f"AssetLookupResult docstring must contain the phrase {_CANONICAL_PHRASE!r} "
        "so the snapshot-vs-walk-axis distinction stays explicit and a future "
        "edit cannot silently re-invite a walk-axis field. See chain-walk Anti-hook 5."
    )
