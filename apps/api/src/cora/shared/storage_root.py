"""Matching a filesystem path against a facility's configured storage roots.

Lives in `cora.shared` (`depends_on = []`) rather than in either BC
because three layers need the SAME answer and would otherwise each
derive it: `cora.api`'s `RunWitnessRecorder` records which root a
capture path was observed under, `cora.data`'s locator embeds that root
in an indirect locator, and `cora.run`'s vault persists and keys on it.
The Run aggregate is restricted to `cora.infrastructure` + `cora.shared`,
so a home in either BC would put the definition of `root` out of reach
of the store that keys on it, which is exactly how a recorded location
and a minted location drift apart into a locator that resolves to
nothing.

Normalization belongs here for the same reason. A trailing slash in a
configured root is a legal, plausible thing for an operator to type, and
if one caller strips it while another does not, the two produce
different strings for the same directory and every lookup misses.
"""

from __future__ import annotations


def normalize_storage_root(root: str) -> str:
    """The canonical form of a configured storage root.

    Trailing slashes are stripped so `/local1/2BM/` and `/local1/2BM`
    are one root, not two. A root of `/` normalizes to the empty
    string, which callers must reject rather than store: the vault's
    own CHECK constraint forbids it.
    """
    return root.rstrip("/")


def path_is_under_root(path: str, root: str) -> bool:
    """Whether `path` is `root` itself or lies beneath it.

    Compares whole path segments, so `/local1/2BM` does NOT match
    `/local1/2BMX/scan.h5`: a plain `startswith` would treat a sibling
    directory whose name merely shares a prefix as being inside the
    allowlisted tier.
    """
    normalized = normalize_storage_root(root)
    return path == normalized or path.startswith(normalized + "/")


def require_nonempty_absolute_root(root: str, *, label: str) -> None:
    """Raise `ValueError` unless `root` is absolute and does not
    normalize to the empty string.

    Shared by three callers that enforce this same shape rule but then
    diverge: `Settings._validate_posix_checksum_roots` and
    `_validate_scan_probe_allowed_roots` call this then store `root` AS
    TYPED, normalizing only at comparison time via `path_is_under_root`;
    `CaptureScanIngestorBinding`'s locations validator calls this then
    stores `normalize_storage_root(root)` itself, since that field is
    later looked up by exact key rather than compared path-by-path, so
    it must be normalization-stable at rest, not just at compare time.
    `label` names the field and, where the caller has one, the entry
    itself (for example `"posix_checksum_roots entry"`), so the raised
    message reads naturally as `f"{label} {root!r} ..."`.
    """
    if not root.startswith("/"):
        msg = f"{label} {root!r} is not an absolute path."
        raise ValueError(msg)
    if not normalize_storage_root(root):
        msg = (
            f"{label} {root!r} normalizes to the empty string. A root must "
            "name a facility-level storage tier, not the filesystem root itself."
        )
        raise ValueError(msg)


def matched_storage_root(path: str, roots: tuple[str, ...]) -> str | None:
    """The first root in `roots` that `path` falls under, normalized.

    Returns `None` when none match, which every caller treats as a
    refusal rather than a default: a fabricated root would be embedded
    verbatim in a locator and recorded verbatim in the vault, and both
    are worse than declining.

    The return is normalized so that the recorder, the locator and the
    vault all hold byte-identical strings for one directory regardless
    of how the deployment spelled it in settings.
    """
    for root in roots:
        if path_is_under_root(path, root):
            return normalize_storage_root(root)
    return None


__all__ = [
    "matched_storage_root",
    "normalize_storage_root",
    "path_is_under_root",
    "require_nonempty_absolute_root",
]
