#!/usr/bin/env bash
# Flags a changed migration file that carries irreversible or locking-prone
# DDL with no explicit `-- atlas:safety:allow=<reason>` opt-out.
#
# A bare `--` truncates the rest of a line before matching (same effect as
# `sed 's/--.*//'`; this migration corpus has no `/* */` block comments, so
# that single-line rule is sufficient), so a keyword named only in prose
# never trips the scan.
#
# TRUNCATE only counts when it leads a statement (the first token after
# the start of a line, or after a semicolon). A GRANT/REVOKE privilege
# list that merely names TRUNCATE among the privileges it grants or
# removes is not a TRUNCATE statement (REVOKE ... TRUNCATE ... is in fact
# safety-increasing, not destructive) and must not match. DROP TABLE,
# DROP COLUMN and ALTER COLUMN ... TYPE never appear as items in a
# privilege list, so they keep the plain anywhere-on-the-line match.
#
# The escape hatch is accepted either on the offending line itself or on
# the nearest non-blank line above it: 4 of the 6 existing uses in this
# repo's migrations put the marker on a standalone comment line above the
# statement, separated from it by one blank line (a paragraph break in the
# migration's header comment), so only accepting a literal same-line or
# strict-N-minus-1 form would leave those precedents with no working
# opt-out.
#
# Usage: scan_destructive_ddl.sh <repo-root> <repo-root-relative-sql-file>...
# File arguments must be relative to <repo-root> so the emitted
# `::error file=` annotation resolves to the right file in the GitHub UI.

set -euo pipefail

root="$1"
shift

marker='atlas:safety:allow='
violations=0

# Walks backward from just above $2 in file $1, skipping blank
# (whitespace-only) lines, and prints the first non-blank line found (or
# nothing, if the file starts with $2). That is the line a reader would
# call "immediately before" the statement once blank paragraph breaks in
# a header comment are not counted as content.
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

    # One `sed` pass strips comments for the whole file (line count is
    # preserved, so line numbers below still line up with the original
    # file), then one `grep -n` finds every candidate line. Both run once
    # per file rather than once per line, which matters once this is run
    # over the whole corpus rather than the 1-2 files a real PR touches.
    stripped_content=$(sed 's/--.*//' "$path")
    forbidden='\bDROP[[:space:]]+TABLE\b|\bDROP[[:space:]]+COLUMN\b|\bALTER[[:space:]]+COLUMN\b.*\bTYPE\b|(^|;)[[:space:]]*TRUNCATE\b'
    matches=$(grep -n -i -E "$forbidden" <<<"$stripped_content" || true)

    [ -z "$matches" ] && continue

    while IFS= read -r m; do
        [ -z "$m" ] && continue
        line_no="${m%%:*}"
        content="${m#*:}"
        lower_content=$(tr '[:upper:]' '[:lower:]' <<<"$content")
        case "$lower_content" in
            *drop*table*) reason="DROP TABLE" ;;
            *drop*column*) reason="DROP COLUMN" ;;
            *alter*column*type*) reason="ALTER COLUMN ... TYPE" ;;
            *) reason="TRUNCATE" ;;
        esac

        original=$(sed -n "${line_no}p" "$path")
        prev_original=$(find_prev_nonblank_line "$path" "$line_no")

        if grep -q -i -F -- "$marker" <<<"$original" || grep -q -i -F -- "$marker" <<<"$prev_original"; then
            :
        else
            echo "::error file=${f},line=${line_no}::Destructive DDL ($reason) with no atlas:safety:allow marker on this line or the nearest non-blank line above it." >&2
            violations=$((violations + 1))
        fi
    done <<<"$matches"
done

if [ "$violations" -gt 0 ]; then
    echo "Safety scan: $violations violation(s) found." >&2
    exit 1
fi

echo "Safety scan passed: no unmarked destructive DDL in changed migrations."
