# Repo guidance

This file is read by Claude Code (and other agents that respect `CLAUDE.md`). Keep it as a pointer file, not a long doc; the real conventions live in `docs/reference/`.

## Conventions

- **Codebase layout, naming, BC structure, patterns**: [docs/reference/](docs/reference/index.md)
- **Identifiers, units, personal data, schema-validated values, documentation**: [docs/reference/conventions.md](docs/reference/conventions.md)
- **Docstring + comment + test-doc style specifically**: [docs/reference/conventions.md#documentation](docs/reference/conventions.md#documentation)
- **Glossary**: [docs/reference/glossary.md](docs/reference/glossary.md)

## Hard rules carried into every change

- No phase / iteration / audit tags (`Phase 8f-d`, `Iter B-3`, `DLM-A`, `audit-2026-...`) in source. Git log and `project_phase_plan.md` are the right home.
- No emoji anywhere in source — comments, docstrings, log strings, error messages, `Field(description=...)`.
- No em dashes in user-facing prose; use commas, colons, or rephrase.
- Default to no `#` comments. Add one only when the WHY is non-obvious.
- Test names carry scenarios (`test_<subject>_<scenario>_<expectation>`); per-test docstrings stay rare.

## Memory hygiene

Auto-memory grows monotonically without a forcing function. These rules curb drift between sessions. They apply to `~/.claude/projects/-Users-dgursoy-Documents-Github-cora/memory/`.

- Before creating a new memo, grep MEMORY.md for the topic; prefer edit-in-place over a new file.
- When tagging a memo SUPERSEDED, move its index entry to `## Reference` in the same edit.
- After a memo's content reaches SHIPPED and the work has been on main for 30+ days, demote its index entry to `## Reference`.
- Any index description containing a count, phase tag, or date older than 7 days requires a Read of the underlying file before quoting in chat.
- Mutable phase status does not belong in index descriptions; the index carries the durable claim, the file carries the status.
- Memo files over ~300 lines: split into 2-3 sibling files linked from the first.

## Commits

One-line subject, body explains WHY. Recent commits set the tone — `git log --oneline -10`.

## Reviewer subagents

- [`naming-r3-reviewer`](.claude/agents/naming-r3-reviewer.md): auto-invoked on rename or new-name commits (aggregate fields, event/command classes, slice directories, aggregate types, agent types). Checks R1-R5 with an explicit guard against the R3 noun-LAST trap. First committed reviewer; more axes added only after a rule-of-three trigger fires.
