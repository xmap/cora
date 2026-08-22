"""Unit: `is_safe_path_segment`, the rule both sides of the probe seam apply.

Tested directly rather than only through `_remote_scan_probe._handle`
because the function is in `cora.shared` for the express purpose of
being applied twice, and a rule with two callers needs its own
statement of what it permits.
"""

import pytest

from cora.shared.path_segment import MAX_PATH_SEGMENT_LENGTH, is_safe_path_segment


@pytest.mark.parametrize(
    "value",
    [
        "2026-08",
        "2026-08-Haridy-1015116",
        "scan_005.h5",
        "data",
        "-1015116",
        "a" * MAX_PATH_SEGMENT_LENGTH,
        "file.with.many.dots",
        "...",
    ],
)
def test_an_ordinary_single_entry_name_is_safe(value: str) -> None:
    assert is_safe_path_segment(value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        ".",
        "..",
        "../etc",
        "etc/passwd",
        "/absolute",
        "trailing/",
        "back\\slash",
        "nul\x00byte",
        " leading",
        "trailing ",
        "\ttab",
        "a" * (MAX_PATH_SEGMENT_LENGTH + 1),
    ],
)
def test_a_value_that_could_name_something_else_is_refused(value: str) -> None:
    assert not is_safe_path_segment(value)


def test_three_dots_is_safe_though_one_and_two_are_not() -> None:
    """`.` and `..` are refused because the filesystem gives them
    meaning, not because dots are suspicious. `...` is an ordinary
    directory name and refusing it would be superstition, so the rule
    is an exact-match set rather than a prefix or a character ban."""
    assert not is_safe_path_segment(".")
    assert not is_safe_path_segment("..")
    assert is_safe_path_segment("...")
