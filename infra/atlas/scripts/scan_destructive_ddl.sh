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
# safety-increasing, not destructive) and must not match. DROP TABLE and
# DROP COLUMN never appear as items in a privilege list, so they keep the
# plain anywhere-on-the-line match.
#
# ALTER COLUMN ... TYPE only counts when the same line carries no USING
# clause: an explicit USING spells out the exact conversion, which is the
# documented, reviewed way to do this, not a bare unannounced type change.
# This check is line-scoped, so a USING clause written on a continuation
# line of a multi-line ALTER COLUMN statement would not be seen here; this
# corpus's two USING occurrences are both single-line.
#
# The escape hatch is same-line only. Measured against this corpus with a
# same-line-only marker: 5 violations, identical to the widened form that
# also accepted a marker on the line before. Nothing here currently
# depends on a backward-lookback marker, and a lookback marker on this
# script's forbidden statements (DROP TABLE, DROP COLUMN, ALTER COLUMN,
# TRUNCATE) is far more likely to leak onto an unrelated later statement
# than to legitimately excuse one (see scan_constraint_drops.sh's history
# for why the lookback form needs an extra standalone-comment guard even
# where it is load bearing), so this script does not carry that surface
# at all.
#
# Usage: scan_destructive_ddl.sh <repo-root> <repo-root-relative-sql-file>...
# File arguments must be relative to <repo-root> so the emitted
# `::error file=` annotation resolves to the right file in the GitHub UI.

set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=_scan_common.sh
source "$script_dir/_scan_common.sh"

root="$1"
shift

violations=0

for f in "$@"; do
    path="$root/$f"
    if ! require_file "$root" "$f"; then
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
            *alter*column*type*)
                case "$lower_content" in
                    *using*) continue ;;
                esac
                reason="ALTER COLUMN ... TYPE without USING"
                ;;
            *drop*table*) reason="DROP TABLE" ;;
            *drop*column*) reason="DROP COLUMN" ;;
            *) reason="TRUNCATE" ;;
        esac

        original=$(sed -n "${line_no}p" "$path")

        if grep -q -i -F -- "$marker" <<<"$original"; then
            :
        else
            echo "::error file=${f},line=${line_no}::Destructive DDL ($reason) with no atlas:safety:allow marker on this line." >&2
            violations=$((violations + 1))
        fi
    done <<<"$matches"
done

if [ "$violations" -gt 0 ]; then
    echo "Safety scan: $violations violation(s) found." >&2
    exit 1
fi

echo "Safety scan passed: no unmarked destructive DDL in changed migrations."
