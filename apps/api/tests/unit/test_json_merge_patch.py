"""Unit tests for the shared RFC 7396 JSON Merge Patch implementation.

`cora.shared.json_merge_patch.merge_patch` was hoisted at the
rule-of-three trigger once the third call site landed (originally
lived in `cora.equipment.aggregates.asset.settings_validation`). The
tests below were moved with the implementation; the equipment slice's
test file no longer carries them.

Pins RFC 7396 semantics + the deepcopy invariants that prevent the
returned dict from sharing nested mutable references with `current`
or `patch` (caller mutations of the result must not propagate back).
"""

from typing import Any

import pytest

from cora.shared.json_merge_patch import merge_patch


@pytest.mark.unit
def test_merge_patch_sets_new_key() -> None:
    assert merge_patch({}, {"a": 1}) == {"a": 1}


@pytest.mark.unit
def test_merge_patch_replaces_existing_key() -> None:
    assert merge_patch({"a": 1}, {"a": 2}) == {"a": 2}


@pytest.mark.unit
def test_merge_patch_null_deletes_existing_key() -> None:
    assert merge_patch({"a": 1, "b": 2}, {"a": None}) == {"b": 2}


@pytest.mark.unit
def test_merge_patch_null_on_absent_key_is_no_op() -> None:
    assert merge_patch({"a": 1}, {"b": None}) == {"a": 1}


@pytest.mark.unit
def test_merge_patch_preserves_absent_keys() -> None:
    assert merge_patch({"a": 1, "b": 2}, {"a": 5}) == {"a": 5, "b": 2}


@pytest.mark.unit
def test_merge_patch_recurses_into_nested_dicts() -> None:
    assert merge_patch({"a": {"x": 1, "y": 2}}, {"a": {"y": 5}}) == {"a": {"x": 1, "y": 5}}


@pytest.mark.unit
def test_merge_patch_null_inside_nested_dict_deletes_nested_key() -> None:
    assert merge_patch({"a": {"x": 1, "y": 2}}, {"a": {"y": None}}) == {"a": {"x": 1}}


@pytest.mark.unit
def test_merge_patch_returns_new_dict_does_not_mutate_input() -> None:
    current = {"a": 1}
    patch = {"b": 2}
    result = merge_patch(current, patch)
    assert current == {"a": 1}
    assert patch == {"b": 2}
    assert result == {"a": 1, "b": 2}


@pytest.mark.unit
def test_merge_patch_replaces_dict_with_scalar() -> None:
    """Patching a dict-typed key with a scalar replaces (not merges)."""
    assert merge_patch({"a": {"x": 1}}, {"a": 42}) == {"a": 42}


@pytest.mark.unit
def test_merge_patch_does_not_alias_nested_dicts_from_current() -> None:
    """Pinned: the result must be deeply independent of `current`.
    Mutating a nested dict in the returned result must NOT propagate
    back into `current`. Pre-fix the implementation passed nested
    dicts by reference (shallow copy at top level only), which would
    let event-payload mutations corrupt prior Asset state across
    folds."""
    current: dict[str, Any] = {"a": {"x": 1, "y": 2}, "b": "scalar"}
    patch: dict[str, Any] = {"c": 3}  # patch doesn't touch `a`
    result = merge_patch(current, patch)
    # Mutate the nested dict in the result.
    result["a"]["x"] = 999
    # `current` must NOT see the mutation.
    assert current["a"]["x"] == 1


@pytest.mark.unit
def test_merge_patch_does_not_alias_nested_dicts_from_patch() -> None:
    """Symmetric pin: mutating a nested dict in the returned result
    must NOT propagate back into `patch` either."""
    current: dict[str, Any] = {}
    patch = {"a": {"x": 1}}
    result = merge_patch(current, patch)
    result["a"]["x"] = 999
    assert patch["a"]["x"] == 1
