#!/usr/bin/env bash
# Flags a changed migration file that drops a constraint or an index and
# adds nothing back in the same file, with no explicit
# `-- atlas:safety:allow=<reason>` opt-out.
#
# `ADD CONSTRAINT`, `ADD PRIMARY KEY`, `ADD UNIQUE`, `ADD CHECK`,
# `ADD FOREIGN KEY` and `CREATE INDEX` (unique or not) all count as
# adding something back. Plain `CREATE INDEX` counts because dropping an
# index and recreating it, even without UNIQUE, is a deliberate
# replacement, not a bare removal; the corpus's own DROP-INDEX-then-
# CREATE-INDEX idiom at 20260602100000 recreates a plain, non-unique
# index on purpose (the comment there says so directly).
#
# This check does not know whether a dropped index was UNIQUE: a bare
# `DROP INDEX` statement carries no such information, and the CREATE that
# originally added the uniqueness guarantee usually lives in a different,
# older migration file entirely. Treating every dropped index as if it
# might have enforced a guarantee is a deliberately conservative default,
# not a claim that every flagged index drop removes a real integrity
# guarantee.
#
# The "adds something back" check is file-scoped, not name-paired: it
# only asks whether an add-back token appears ANYWHERE in the file, not
# whether it restores the SPECIFIC thing that was dropped. Known limits,
# accepted rather than engineered around:
#
#   - File-scoped pairing cannot distinguish "drop A, add A back" from
#     "drop A, add unrelated B". Tightening by constraint name would
#     false-positive on renames, which are most of the real cases in
#     this corpus (see 20260519233000, 20260602000000, 20260611120000).
#   - A DROP CONSTRAINT / DROP INDEX or an ADD CONSTRAINT / ADD ... split
#     across two lines evades this line-based grep entirely (no
#     adjacent-line join is attempted here; an earlier version of this
#     script had one, but disabling it never changed the corpus result,
#     so it was removed rather than kept as exemption surface that does
#     nothing).
#   - A constraint dropped in one new file and re-added in a second new
#     file in the same pull request is refused, even though both files
#     are passed to this script in the same invocation: the add-back
#     search is per file, not per invocation.
#   - `sed 's/--.*//'` deletes everything after a `--` inside a string
#     literal too (for example inside a `COMMENT ON ... IS '...'` value
#     that itself contains `--`). None exist in this corpus today.
#
# The escape hatch is accepted on the offending DROP line itself, or on
# the nearest non-blank line above it PROVIDED that line is a standalone
# comment (trimmed, it starts with `--`): this repo's own DROP-INDEX
# precedents put the marker on such a comment line, separated from the
# statement by one blank line. A marker riding as a trailing comment on a
# DIFFERENT SQL statement is not read as covering the next statement down
# just because it happens to be the nearest non-blank line above it;
# without that guard a marked DROP would silently exempt an unrelated,
# unmarked DROP immediately below it.
#
# Usage: scan_constraint_drops.sh <repo-root> <repo-root-relative-sql-file>...
# File arguments must be relative to <repo-root> so the emitted
# `::error file=` annotation resolves to the right file in the GitHub UI.

set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=_scan_common.sh
source "$script_dir/_scan_common.sh"

root="$1"
shift

drop_pattern='\bDROP[[:space:]]+CONSTRAINT\b|\bDROP[[:space:]]+INDEX\b'
addback_pattern='\bADD[[:space:]]+CONSTRAINT\b|\bADD[[:space:]]+PRIMARY[[:space:]]+KEY\b|\bADD[[:space:]]+UNIQUE\b|\bADD[[:space:]]+CHECK\b|\bADD[[:space:]]+FOREIGN[[:space:]]+KEY\b|\bCREATE[[:space:]]+(UNIQUE[[:space:]]+)?INDEX\b'
violations=0

for f in "$@"; do
    path="$root/$f"
    if ! require_file "$root" "$f"; then
        violations=$((violations + 1))
        continue
    fi

    stripped_content=$(sed 's/--.*//' "$path")

    drops=$(grep -n -i -E "$drop_pattern" <<<"$stripped_content" || true)
    [ -z "$drops" ] && continue

    if grep -q -i -E "$addback_pattern" <<<"$stripped_content"; then
        continue
    fi

    while IFS= read -r m; do
        [ -z "$m" ] && continue
        line_no="${m%%:*}"
        content="${m#*:}"
        lower_content=$(tr '[:upper:]' '[:lower:]' <<<"$content")
        case "$lower_content" in
            *drop*constraint*) reason="DROP CONSTRAINT" ;;
            *) reason="DROP INDEX" ;;
        esac

        original=$(sed -n "${line_no}p" "$path")
        prev_original=$(find_prev_nonblank_line "$path" "$line_no")

        marker_hit=false
        if grep -q -i -F -- "$marker" <<<"$original"; then
            marker_hit=true
        elif is_comment_only_line "$prev_original" && grep -q -i -F -- "$marker" <<<"$prev_original"; then
            marker_hit=true
        fi

        if [ "$marker_hit" = true ]; then
            :
        else
            echo "::error file=${f},line=${line_no}::${reason} with nothing added back in this file and no atlas:safety:allow marker on this line or on the nearest standalone comment line above it." >&2
            violations=$((violations + 1))
        fi
    done <<<"$drops"
done

if [ "$violations" -gt 0 ]; then
    echo "Constraint-drop scan: $violations violation(s) found." >&2
    exit 1
fi

echo "Constraint-drop scan passed: every dropped constraint or index either has a same-file add-back or an atlas:safety:allow marker."
