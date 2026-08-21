#!/usr/bin/env bash
# Flags a changed migration file that drops a constraint or a unique index
# and adds nothing back in the same file, with no explicit
# `-- atlas:safety:allow=<reason>` opt-out.
#
# `ADD CONSTRAINT`, `ADD PRIMARY KEY`, `ADD UNIQUE`, `ADD CHECK`,
# `ADD FOREIGN KEY` and `CREATE UNIQUE INDEX` all count as adding
# something back. The last one matters because this repo's own
# DROP-INDEX-then-CREATE-UNIQUE-INDEX idiom (swapping a unique index's
# definition) is a legitimate, non-destructive replacement pattern, not a
# bare removal.
#
# The "adds something back" check is file-scoped, not name-paired: it
# only asks whether an add-back token appears ANYWHERE in the file, not
# whether it restores the SPECIFIC thing that was dropped. Two known
# limits follow from that and are accepted rather than engineered around:
#
#   - File-scoped pairing cannot distinguish "drop A, add A back" from
#     "drop A, add unrelated B". Tightening by constraint name would
#     false-positive on renames, which are most of the real cases in
#     this corpus (see 20260519233000, 20260602000000, 20260611120000).
#   - A DROP CONSTRAINT / DROP INDEX split across lines can still evade
#     this line-based grep. `ADD` split from `CONSTRAINT` (and the other
#     add-back keyword pairs) IS handled, by also matching each pair of
#     adjacent lines joined together, because that split is the one this
#     corpus's style actually risks (a multi-line ALTER TABLE ... ADD
#     CONSTRAINT block); the drop side is not, because this corpus never
#     splits DROP from CONSTRAINT/INDEX and over-engineering a symmetric
#     join for the drop side would also let two unrelated single-line
#     DROP statements in a row combine into a spurious match.
#
# The escape hatch is accepted on the offending DROP line itself or on
# the nearest non-blank line above it, matching scan_destructive_ddl.sh:
# this repo's own DROP-INDEX precedents put the marker on a standalone
# comment line separated from the statement by one blank line.
#
# Usage: scan_constraint_drops.sh <repo-root> <repo-root-relative-sql-file>...
# File arguments must be relative to <repo-root> so the emitted
# `::error file=` annotation resolves to the right file in the GitHub UI.

set -euo pipefail

root="$1"
shift

marker='atlas:safety:allow='
drop_pattern='\bDROP[[:space:]]+CONSTRAINT\b|\bDROP[[:space:]]+INDEX\b'
addback_pattern='\bADD[[:space:]]+CONSTRAINT\b|\bADD[[:space:]]+PRIMARY[[:space:]]+KEY\b|\bADD[[:space:]]+UNIQUE\b|\bADD[[:space:]]+CHECK\b|\bADD[[:space:]]+FOREIGN[[:space:]]+KEY\b|\bCREATE[[:space:]]+UNIQUE[[:space:]]+INDEX\b'
violations=0

# Walks backward from just above $2 in file $1, skipping blank
# (whitespace-only) lines, and prints the first non-blank line found (or
# nothing, if the file starts with $2).
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

for f in "$@"; do
    path="$root/$f"
    if [ ! -f "$path" ]; then
        echo "::error file=${f}::Listed as a changed migration but not found on disk." >&2
        violations=$((violations + 1))
        continue
    fi

    stripped_content=$(sed 's/--.*//' "$path")

    drops=$(grep -n -i -E "$drop_pattern" <<<"$stripped_content" || true)
    [ -z "$drops" ] && continue

    # Adjacent-line join catches an add-back keyword pair split across two
    # lines (e.g. `ADD` at end of line, `CONSTRAINT foo` on the next).
    joined_pairs=$(awk '{ if (NR > 1) print prev " " $0; prev = $0 }' <<<"$stripped_content")

    has_addback=false
    if grep -q -i -E "$addback_pattern" <<<"$stripped_content" \
        || grep -q -i -E "$addback_pattern" <<<"$joined_pairs"; then
        has_addback=true
    fi

    if [ "$has_addback" = true ]; then
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

        if grep -q -i -F -- "$marker" <<<"$original" || grep -q -i -F -- "$marker" <<<"$prev_original"; then
            :
        else
            echo "::error file=${f},line=${line_no}::${reason} with nothing added back in this file and no atlas:safety:allow marker on this line or the nearest non-blank line above it." >&2
            violations=$((violations + 1))
        fi
    done <<<"$drops"
done

if [ "$violations" -gt 0 ]; then
    echo "Constraint-drop scan: $violations violation(s) found." >&2
    exit 1
fi

echo "Constraint-drop scan passed: every dropped constraint or unique index either has a same-file add-back or an atlas:safety:allow marker."
