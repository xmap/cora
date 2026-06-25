# Papers

LaTeX paper sources. Each subdirectory is one paper. The folder name is the
slug; it becomes the URL path and the source link forever. This mirrors how
[`talks/`](../talks/README.md) works, with one difference for now: papers are
surfaced **source-only** (a card on the site plus a link to the source on
GitHub). Building a downloadable PDF in CI is a documented later step, not yet
wired (see "How papers are surfaced" below).

## Add a new paper

1. Create `papers/<slug>/` (see naming below), or copy
   `2026-vaxautosci-scrubber/` as a template.
2. Write the paper in `main.tex` with references in `refs.bib`. Drop the
   target venue's LaTeX class files into the folder (we do not vendor them).
3. Add a card to [`docs/papers.md`](../docs/papers.md).
4. Commit sources. Nothing is auto-built today; the card links the source.

## Naming convention

Year-first, kebab-case: **`YYYY-<venue>-<short-tag>`** (e.g.
`2026-vaxautosci-scrubber`). Same rule as talks:

- Lowercase kebab-case (no `_`, no spaces, no caps).
- Under 30 characters. URLs and any future PDF filenames look bad long.
- `ls papers/` then sorts chronologically.

Examples:

| Slug | Venue | Year |
|---|---|---|
| `2026-vaxautosci-scrubber` | VAxAutoSci (IEEE VIS workshop) | 2026 |
| `2027-scipy-provenance` | SciPy | 2027 |

## Per-paper README

Each `papers/<slug>/` folder has its own `README.md` covering:

- Lead motivator (one sentence) and the core thesis.
- Target venue, deadline, and current status.
- Section map and figure inventory.
- Local build instructions and the camera-ready checklist.

[2026-vaxautosci-scrubber/README.md](2026-vaxautosci-scrubber/README.md) is a
working template.

## What gets tracked

Sources only: `main.tex`, `refs.bib`, `README.md`, `notes/`, and `figures/`
(source figures). Prose may be split into `sections/*.tex` fragments, with
`main.tex` (the submission) and an optional `preview.tex` (a two-column proxy
build, e.g. under `IEEEtran`, that needs no venue class) reading the same
fragments so the text does not drift. LaTeX build artifacts (`*.aux`, `*.log`, `*.bbl`, `*.pdf`, and
friends) are gitignored at the repo root. The venue's class and bibstyle files
(`*.cls`, `*.bst`) may be vendored per paper when the kit is freely
redistributable: the VAxAutoSci pilot vendors the official VGTC conference
template (`vgtc.cls` + `abbrv-doi*.bst`); otherwise the author drops them in
locally.

## How papers are surfaced

**Today (lightweight):** a hand-authored card in
[`docs/papers.md`](../docs/papers.md), shown as a top-level "Papers" tab on the
site, linking to the paper's source tree on GitHub. No PDF, no CI build. This
keeps a pre-submission paper visible as part of the CORA ecosystem without
standing up a TeX pipeline before there is a compiled draft.

**Camera-ready step (deferred, do this when a paper is accepted/final):**

1. Track or generate `papers/<slug>/<slug>.pdf`.
2. Add a `Build papers` loop to
   [`.github/workflows/docs.yml`](../.github/workflows/docs.yml), mirroring the
   `Build talks` step: iterate `papers/*/`, compile with a LaTeX action, and
   copy the PDF to `site/papers/<slug>/<slug>.pdf`.
3. Add `papers/**` to that workflow's `on.push.paths`.
4. Update the card in `docs/papers.md` to add a PDF download link and point
   "Open" at the built `papers/<slug>/` path.
