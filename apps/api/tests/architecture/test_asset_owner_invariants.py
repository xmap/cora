"""Architecture fitness tests pinning the AssetOwner design locks.

Four checks per Section 9.11 of project_asset_owner_design:

  1. `AssetOwnerIdentifierType` is a `@dataclass(frozen=True)`, NOT a
     `StrEnum` (Lock 4 / F6.3: PIDINST 5.3.1 is deliberately free
     text).
  2. PIDINST 1-n cardinality is enforced at the serializer, NOT at
     the remove_asset_owner decider (Lock 7). The remove decider's
     source must not raise on empty owners; the serializer's source
     must contain the `OwnerStateNotAvailableError` raise on empty.
  3. The slice-E `AssetPidinstView` builder, when it lands, must not
     re-sort owners (Lock 1's projection-time-sort placement). For
     slice D the check is forward-only: the current
     `_pidinst_serializer.py` must not sort owners by name.
  4. No role-taxonomy literal (`contributor_type` / `role`) leaks
     into the Equipment BC source (Defer-3).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architecture.conftest import tracked_python_files

_REPO_ROOT = Path(__file__).resolve().parents[4]
_EQUIPMENT_DIR = _REPO_ROOT / "apps" / "api" / "src" / "cora" / "equipment"

_STATE_PATH = _EQUIPMENT_DIR / "aggregates" / "asset" / "state.py"
_REMOVE_DECIDER_PATH = _EQUIPMENT_DIR / "features" / "remove_asset_owner" / "decider.py"
_SERIALIZER_PATH = _EQUIPMENT_DIR / "_pidinst_serializer.py"


@pytest.mark.architecture
def test_asset_owner_identifier_type_is_not_an_enum() -> None:
    """Lock 4: `AssetOwnerIdentifierType` is a free-text frozen
    dataclass, NOT a StrEnum (PIDINST 5.3.1 is deliberately open per
    F6.3). The bare-source greps below are sufficient: a future
    refactor that changed the type to `class AssetOwnerIdentifierType(StrEnum):`
    would fail this check immediately."""
    text = _STATE_PATH.read_text(encoding="utf-8")
    assert "class AssetOwnerIdentifierType:" in text
    # The bounded-text VOs all wear @dataclass(frozen=True) and a
    # `value: str` attribute. Pin both so a future refactor that
    # collapses the type to a NewType or StrEnum subclass is rejected.
    assert "@dataclass(frozen=True)\nclass AssetOwnerIdentifierType:" in text
    assert "AssetOwnerIdentifierType(StrEnum)" not in text
    assert "class AssetOwnerIdentifierType(StrEnum):" not in text


@pytest.mark.architecture
def test_pidinst_cardinality_enforced_at_serializer_not_aggregate() -> None:
    """Lock 7: removing the last owner is allowed at the aggregate.
    PIDINST 1-n MANDATORY cardinality is enforced at the serializer's
    `OwnerStateNotAvailableError` raise site, not at the
    remove_asset_owner decider."""
    decider_src = _REMOVE_DECIDER_PATH.read_text(encoding="utf-8")
    # The decider must NOT raise any owner-cardinality-minimum guard.
    # Tokens that would only ever appear in a guard implementation, not
    # in narrative docstrings.
    forbidden_tokens = (
        "raise LastOwnerForbidden",
        "raise OwnerStateNotAvailable",
        "len(state.owners) < 1",
        "len(state.owners) <= 1",
        "len(state.owners) == 1",
        "if not state.owners",
        "if len(state.owners) == 0",
    )
    for token in forbidden_tokens:
        assert token not in decider_src, (
            f"remove_asset_owner decider source contains forbidden cardinality "
            f"guard token {token!r}; Lock 7 places the 1-n check at the "
            "serializer, not the decider."
        )
    serializer_src = _SERIALIZER_PATH.read_text(encoding="utf-8")
    assert "OwnerStateNotAvailableError" in serializer_src, (
        "PIDINST serializer must continue to raise "
        "OwnerStateNotAvailableError on empty owners (Lock 14)."
    )


@pytest.mark.architecture
def test_asset_pidinst_serializer_does_not_resort_owners() -> None:
    """Lock 1: ordering is stamped at projection-write time (sort by
    name ASC in the JSONB column). The serializer must not re-sort
    owners; sorting at serialization would mask projection-time drift.
    Forward-only check: the slice-E view-builder (when it lands) will
    inherit this constraint via the same module."""
    serializer_src = _SERIALIZER_PATH.read_text(encoding="utf-8")
    # The serializer iterates `view.owners`; a re-sort would look like
    # `sorted(view.owners` or `sorted(owners,`. Forbid both shapes.
    assert "sorted(view.owners" not in serializer_src, (
        "PIDINST serializer must not re-sort `view.owners`; Lock 1 places "
        "the sort at projection-write time."
    )
    assert "sorted(owners," not in serializer_src, (
        "PIDINST serializer must not re-sort owners; Lock 1 places the "
        "sort at projection-write time."
    )


_ROLE_TAXONOMY_ALLOW_PATHS: frozenset[str] = frozenset(
    {
        # The PIDINST intermediate-types docstring narrates the slice
        # 6 DataCite mapping `contributorType=HostingInstitution` as
        # context for future implementers; it does NOT declare a role
        # field on the intermediate (Defer-3 is about aggregate /
        # event-payload state, not docstrings). Allow-listed for the
        # documentary reference; remove this entry when slice 6 lands
        # and replace the docstring mention with a code-side import.
        "apps/api/src/cora/equipment/_pidinst_types.py",
    }
)


@pytest.mark.architecture
def test_no_asset_owner_role_taxonomy_literal() -> None:
    """Defer-3: no owner-role / contributor_type taxonomy in v1. The
    DataCite mint adapter (future slice 6) hardcodes
    `contributorType=HostingInstitution`. Until then, no role-taxonomy
    literal may leak into the Equipment BC source (with a narrow
    docstring-only allow-list for the slice-6 mapping reference)."""
    forbidden_substrings = (
        "owner_role",
        "owner_kind",
        "ownerRole",
        "contributorType",
        "contributor_type",
    )
    hits: list[tuple[Path, int, str]] = []
    for path in tracked_python_files():
        # Restrict to Equipment BC source.
        if "equipment" not in path.parts:
            continue
        # The fitness file itself names the forbidden tokens in its
        # docstring; allow-list it.
        if path == Path(__file__):
            continue
        try:
            relative = path.relative_to(_REPO_ROOT).as_posix()
        except ValueError:
            relative = path.as_posix()
        if relative in _ROLE_TAXONOMY_ALLOW_PATHS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            for token in forbidden_substrings:
                if token in line:
                    hits.append((path, line_no, line.strip()))
                    break
    assert hits == [], (
        f"Found {len(hits)} owner-role taxonomy literal(s) in the "
        "Equipment BC; Defer-3 forbids role/contributor_type fields in v1.\n"
        + "\n".join(f"  {p}:{n}: {line}" for p, n, line in hits)
    )
