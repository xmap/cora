"""Unit tests for storage-root matching and normalization.

These moved here from the locator's own tests when the matching left
`cora.data`: three layers (the witness recorder, the locator, the vault)
now read one answer from this module, and the normalization is the part
that has to be identical across them. A root spelled with a trailing
slash in settings must produce the same string the locator embeds and
the vault stores, or every lookup for that tier misses forever.
"""

import pytest

from cora.shared.storage_root import (
    matched_storage_root,
    normalize_storage_root,
    path_is_under_root,
)

pytestmark = pytest.mark.unit

_SCAN = "/local1/2BM/2026-08-Smith-1015116/scan_005.h5"


def test_matched_root_returns_the_second_root_when_the_first_does_not_apply() -> None:
    assert matched_storage_root(_SCAN, ("/local2/2BM", "/local1/2BM")) == "/local1/2BM"


def test_matched_root_refuses_a_path_outside_every_configured_root() -> None:
    assert matched_storage_root(_SCAN, ("/somewhere/else",)) is None


def test_matched_root_refuses_every_path_when_roots_is_empty() -> None:
    """An unconfigured deployment must refuse every path, not treat an
    empty allowlist as matching anything."""
    assert matched_storage_root(_SCAN, ()) is None


def test_matched_root_does_not_treat_a_sibling_directory_as_under_the_root() -> None:
    """`/local1/2BM` must not prefix-match `/local1/2BMX/...`."""
    assert matched_storage_root("/local1/2BMX/2026-08-Smith-1/scan.h5", ("/local1/2BM",)) is None


@pytest.mark.parametrize("configured", ["/local1/2BM", "/local1/2BM/", "/local1/2BM///"])
def test_matched_root_normalizes_however_the_deployment_spelled_it(configured: str) -> None:
    """The bug this function exists to make impossible. Before the
    matching and the normalization lived together, the recorder stored
    the configured string verbatim while the locator embedded an
    rstripped copy, so a single trailing slash in settings meant the
    vault and the locator held different strings for one directory and
    resolution missed permanently, for every run."""
    assert matched_storage_root(_SCAN, (configured,)) == "/local1/2BM"


def test_matched_root_accepts_a_path_equal_to_the_root_itself() -> None:
    assert matched_storage_root("/local1/2BM", ("/local1/2BM",)) == "/local1/2BM"


def test_path_is_under_root_ignores_a_trailing_slash_on_the_root() -> None:
    assert path_is_under_root(_SCAN, "/local1/2BM/")


def test_normalize_reduces_a_bare_slash_to_empty_which_callers_must_reject() -> None:
    """Documented rather than defended here: the vault's CHECK
    constraint forbids an empty root, so a deployment configuring `/`
    fails at the write rather than silently allowlisting the filesystem."""
    assert normalize_storage_root("/") == ""
