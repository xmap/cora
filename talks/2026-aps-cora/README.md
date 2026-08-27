# CORA at the Advanced Photon Source

Twenty-minute, question-first talk about CORA as a system of record for the
experiment. It opens on questions people at a beamline already ask, puts the
object on screen early, then climbs from the questions a logbook can answer to
the ones a record has to answer about itself.

The measured figures throughout come from the live 2-BM deployment.

## Run locally

```bash
npm install
npm run dev    # http://localhost:3030
```

## Build / export

```bash
npm run build  # static site -> ./dist/
npm run export # -> 2026-aps-cora.pdf
```

CI builds and deploys this deck on push to `main`; see
[.github/workflows/docs.yml](../../.github/workflows/docs.yml).

## Shape of the deck

| Slides | What they do |
|---|---|
| 1-9 | The questions, who asks them, and how they get answered today |
| 10-19 | The object: contexts, the record, one agent's tick, one command end to end |
| 20-24 | How it is proved, and what a decade of record would add |
| 25-34 | What a deployment means, then one zoom per context with live counts |
| 35-38 | The agents with a model behind them, and the question they answered |
| 39-43 | What a deployment needs, where this goes next, and the honest limits |

## Colour

Gold (`#8B6914`) is CORA itself and matches the documentation site's brand.
Blue (`#5B8AA6`) marks anything an LLM-backed agent produced: the
`CautionDrafter` and `RunDebriefer` pills on the roster, their passport
entries, and the shortfall episodes on the timeline. The read/write legend on
the agent-tick slides reads "blue reads, gold writes".

Both are defined as tokens in [style.css](style.css), with a dark-mode block
that mirrors every one of them. Change a colour there, not in `slides.md`.

## Title slide

The bookend slides use `hero-typewriter.webp`, the same image as the
documentation site's landing hero. To swap it, replace
`public/hero-typewriter.webp` and update the two `background:` lines in
`slides.md`.

## Speaker notes

This deck ships without presenter notes, so `presenter: false` is set in the
frontmatter. Slidev compiles HTML comments into the public JavaScript bundle,
where anyone can read them, so delivery notes are kept outside this folder
rather than in `slides.md`.

## Lockfile

Never regenerate `package-lock.json` on macOS. An `npm install` on darwin
strips the platform-optional native binary entries that CI needs on linux, and
the deploy then fails. Regenerate in a container instead:

```bash
rm -rf node_modules package-lock.json
docker run --rm -v "$PWD":/work -w /work node:20-bookworm \
  npm install --no-audit --no-fund --package-lock-only
```
