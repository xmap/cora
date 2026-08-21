#!/usr/bin/env bash
# Shared helpers for infra/atlas/scripts/scan_*.sh. Not runnable on its
# own; sourced by each scan script.
#
# Known gaps, shared by every scan that sources this file (stated rather
# than engineered around):
#
#   - `sed 's/--.*//'` deletes everything after a bare `--` on a line,
#     including a `--` that appears inside a string literal (for example
#     a `COMMENT ON ... IS '... -- not a comment ...'` value). This
#     corpus has no such occurrence today, but it is full of long prose
#     `COMMENT ON ... IS '...'` strings, so a future one would silently
#     stop being scanned past that point on the same line.
#   - A keyword split across two lines (`DROP` at the end of one line,
#     `CONSTRAINT foo` on the next) evades every line-based grep here.
#   - Block comments (`/* ... */`) are not stripped; none exist in this
#     corpus today, so this has not produced a false positive, but a
#     future one would not be excluded the way a `--` comment is.

marker='atlas:safety:allow='

# Prints an ::error annotation and returns non-zero when the changed file
# named by $2 (diff-filter=A said it was added) is not actually present
# at $1/$2. Shared because both scan scripts hit this identically when a
# file is renamed or removed between the diff and the scan running.
require_file() {
    local root="$1" f="$2"
    if [ ! -f "$root/$f" ]; then
        echo "::error file=${f}::Listed as a changed migration but not found on disk." >&2
        return 1
    fi
    return 0
}

# Walks backward from just above line $2 in file $1, skipping blank
# (whitespace-only) lines, and prints the first non-blank line found (or
# nothing, if the file starts with line $2).
find_prev_nonblank_line() {
    local path="$1"
    local check_line=$(($2 - 1))
    local text
    while [ "$check_line" -gt 0 ]; do
        text=$(sed -n "${check_line}p" "$path")
        if [ -n "$(printf '%s' "$text" | tr -d '[:space:]')" ]; then
            printf '%s' "$text"
            return 0
        fi
        check_line=$((check_line - 1))
    done
    printf ''
}

# True when $1, once leading whitespace is trimmed, is a comment-only
# line (starts with `--`). A backward-found line only counts as a valid
# escape-hatch marker when it is a dedicated standalone comment: a
# trailing `-- atlas:safety:allow=...` riding on an unrelated SQL
# statement must not be read as exempting a DIFFERENT statement just
# because that statement happens to sit on the nearest non-blank line
# above it.
is_comment_only_line() {
    local trimmed
    trimmed=$(printf '%s' "$1" | sed -e 's/^[[:space:]]*//')
    case "$trimmed" in
        --*) return 0 ;;
        *) return 1 ;;
    esac
}
