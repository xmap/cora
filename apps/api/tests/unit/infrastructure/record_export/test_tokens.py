"""Unit tests for the per-export UUID surrogate map."""

from cora.infrastructure.record_export import TokenMap

_SOURCE_A = "01900000-0000-7000-8000-0000000000a1"
_SOURCE_B = "01900000-0000-7000-8000-0000000000a2"


def test_none_passes_through_as_none() -> None:
    assert TokenMap().token_uuid(None) is None


def test_same_source_returns_the_same_surrogate_within_one_map() -> None:
    token_map = TokenMap()
    first = token_map.token_uuid(_SOURCE_A)
    second = token_map.token_uuid(_SOURCE_A)
    assert first == second


def test_distinct_sources_get_distinct_surrogates() -> None:
    token_map = TokenMap()
    assert token_map.token_uuid(_SOURCE_A) != token_map.token_uuid(_SOURCE_B)


def test_surrogate_is_never_equal_to_its_source() -> None:
    token_map = TokenMap()
    assert token_map.token_uuid(_SOURCE_A) != _SOURCE_A


def test_surrogate_is_not_derivable_from_its_source() -> None:
    """Two independent TokenMaps produce DIFFERENT surrogates for the
    SAME source: a hash would be deterministic (same input, same
    output, every time) and therefore brute-forceable against a known
    candidate roster. A random mint is not."""
    first_map = TokenMap()
    second_map = TokenMap()
    assert first_map.token_uuid(_SOURCE_A) != second_map.token_uuid(_SOURCE_A)


def test_surrogate_by_source_reflects_every_source_tokenized_so_far() -> None:
    token_map = TokenMap()
    a = token_map.token_uuid(_SOURCE_A)
    b = token_map.token_uuid(_SOURCE_B)
    assert token_map.surrogate_by_source == {_SOURCE_A: a, _SOURCE_B: b}


def test_surrogate_by_source_is_a_copy_not_a_live_view() -> None:
    token_map = TokenMap()
    token_map.token_uuid(_SOURCE_A)
    snapshot = token_map.surrogate_by_source
    snapshot["injected"] = "not-real"
    assert "injected" not in token_map.surrogate_by_source
