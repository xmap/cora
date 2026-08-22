"""Whether a string may be used as one path segment.

Lives in `cora.shared` (`depends_on = []`) because both sides of the
scan-probe seam need the SAME answer: `cora.data.adapters._ssh_probe`
refuses to send an unsafe segment, and `cora.data._remote_scan_probe`
refuses to act on one, on a host where the bytes actually are. Two
copies of this rule would be two chances to disagree, and the side that
matters is whichever one is missing a case.

The values this guards are not authored by CORA. A proposal number
reaches CORA from an EPICS PV writable by anyone with Channel Access,
and a filename reaches it the same way. They are then used to find a
directory on a remote host. Nothing here reaches a shell (the probe
protocol carries JSON on stdin precisely so that it cannot), so this is
not shell-escaping: it is the narrower rule that a value said to name
ONE path segment must not be able to name a different directory, walk
upward, or terminate a C string early.
"""

from __future__ import annotations

MAX_PATH_SEGMENT_LENGTH = 255
"""One segment's byte budget on the filesystems CORA reads (ext4, XFS,
NFS all cap a single name at 255). Longer is not a traversal risk, it
just cannot name a real entry, so refusing early keeps a pointless
round trip off the wire."""

_TRAVERSAL_SEGMENTS = frozenset({".", ".."})


def is_safe_path_segment(value: str) -> bool:
    """Whether `value` names exactly one ordinary path entry.

    Refuses the empty string, `.` and `..`, anything carrying a path
    separator or a NUL, and anything with leading or trailing
    whitespace. Whitespace is refused rather than stripped because a
    caller that meant to send `scan_005.h5 ` and a caller that meant
    `scan_005.h5` want different files, and silently picking one of
    them is how a probe reports a match for a path nobody asked about.

    Backslash is refused alongside `/` even though CORA reads POSIX
    hosts only: it costs nothing, and this rule is the kind that gets
    reused somewhere it was not written for.
    """
    if not value or len(value) > MAX_PATH_SEGMENT_LENGTH:
        return False
    if value in _TRAVERSAL_SEGMENTS:
        return False
    if value != value.strip():
        return False
    return not any(character in value for character in ("/", "\\", "\0"))


__all__ = ["MAX_PATH_SEGMENT_LENGTH", "is_safe_path_segment"]
