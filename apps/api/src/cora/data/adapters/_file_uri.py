"""Shared file:// URI resolution + root confinement for local readers.

Two Data BC adapters read local files from operator-supplied URIs (the
posix checksum adapter and the Data Exchange scan reader), and both
must apply the SAME safety rule: an unbounded reader is a
local-file-read primitive, so a path is only readable when its
RESOLVED realpath sits inside an allowlisted root. Splitting the rule
across two copies is how the two would drift, so it lives once here.

``os.path.realpath`` collapses ``..`` segments and follows symlinks
before the containment check, so neither traversal nor a planted
symlink escapes. An empty allowlist refuses every path.
"""

import os
from dataclasses import dataclass
from urllib.parse import unquote, urlparse


@dataclass(frozen=True)
class ResolvedPath:
    """A file:// URI resolved to a real path inside an allowed root."""

    real_path: str


@dataclass(frozen=True)
class Refused:
    """The URI is not a confined local file; carries the reason."""

    reason: str


def resolve_confined_file_uri(uri: str, allowed_roots: tuple[str, ...]) -> ResolvedPath | Refused:
    """Resolve a ``file://`` URI to a realpath contained by a root.

    Performs filesystem calls (realpath), so call it from a worker
    thread alongside the read it gates, never on the event loop.
    """
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return Refused(reason=f"not a file URI: scheme {parsed.scheme!r}")
    if parsed.netloc not in ("", "localhost"):
        return Refused(reason=f"file URI names a remote host {parsed.netloc!r}")
    raw_path = unquote(parsed.path)
    if not raw_path:
        return Refused(reason="file URI has empty path")

    try:
        real_path = os.path.realpath(raw_path)
    except (OSError, ValueError) as exc:
        # ValueError covers an embedded null byte in the decoded path.
        return Refused(reason=f"path resolution failed: {exc}")

    for root in allowed_roots:
        try:
            if os.path.commonpath([real_path, root]) == root:
                return ResolvedPath(real_path=real_path)
        except ValueError:
            # Mixed absolute/relative or different drives: not contained.
            continue
    return Refused(reason="resolved path is outside the allowed roots")


__all__ = ["Refused", "ResolvedPath", "resolve_confined_file_uri"]
