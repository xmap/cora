# Related-work map

Consolidated from four verified literature passes. Verdict on the two signature
ideas: both have no true VIS/HCI baseline.

- **Content-addressed fidelity badge** (replayed-state == recorded-state,
  verified at the cursor): UNFILLED. Closest = Atlas (mechanism, but
  programmatic, discrete artifacts, no UI).
- **Verdict-colored nested convergence brackets + open-interval interrupted
  markers:** UNFILLED. Closest = PM4Py alignment table (per-step deviation
  color, but positional not iteration axis, no brackets/intervals).
- **Auditable, scrubbable post-hoc replay of a closed-loop run:** UNFILLED.
  Closest interaction = Verdant (scrubber, but re-execution, no fidelity);
  closest posture = Pernosco/rr (record-then-fold, guarantee unrendered).

## Neighborhoods (ordered as the Related Work section flows)

1. **Provenance visualization** (version navigation, not event-log replay):
   VisTrails (IPAW/SIGMOD 2006), Loops (IEEE VIS/TVCG 2024). We fold an
   immutable event record as the scrub interaction, not navigate/diff versions.

2. **Notebook lineage / time travel** (closest overall interaction): Verdant
   (VL/HCC 2018; CHI 2019). Its replay re-executes and ignores original
   dependencies (no fidelity), over one analyst's local notebook; ours folds an
   event-sourced run and certifies the match.

3. **Replay / time-travel debuggers** (closest systems posture): Pernosco/rr
   (rr: USENIX ATC 2017), Whyline (CHI 2008). Deterministic replay is an
   internal guarantee, never rendered; we surface a per-cursor fidelity badge.

4. **Event-sourced scientific replay** (re-execution, not interaction): QIIME 2
   Provenance Replay (PLOS Comput Biol 2023). Regenerates code re-run offline;
   ours is an in-place interactive scrub with a fidelity check at the cursor.

5. **Tamper-evident / verifiable provenance** (closest to the fidelity badge):
   Crosby & Wallach (USENIX Security 2009) and Certificate Transparency (RFC
   6962) verify as machine-checked proofs, no UI; C2PA Verify renders media
   authenticity, not replayed-vs-recorded state; **Atlas** (arXiv 2502.19567,
   2025) does a content-addressed hash-vs-reference check on ML artifacts, but
   programmatic only and over discrete artifacts (PARTIALLY ANTICIPATED at the
   mechanism level, UNFILLED at the visualization level). SWHID supplies the
   content-addressed primitive as a CLI property only.

6. **Reproducibility records and badges** (coarse or metadata-only): CPR (IPAW
   2021), Whole Tale (FGCS 2019), Workflow-Run RO-Crate (PLOS ONE 2024), ACM
   artifact badges. Static reports / immutable snapshots / tolerance-based human
   audit; ours is an automated content-addressed equality check at each cursor
   position.

7. **Conformance checking** (closest to verdict coloring): Rozinat & van der
   Aalst (Information Systems 2008), Berti & van der Aalst (ATAED 2019), PM4Py
   alignment table, online conformance (van Zelst et al., IJDSA 2019). Verdicts
   as static Petri-net overlays or positional move-type coloring, never along an
   iteration axis with interval structure; no interrupted-step representation.
   The surveys (Rehse et al., HICSS-56 2023; Häge & Rehse 2025) declare the
   visual encoding ("How") an open gap. That gift cuts in our favor.

8. **Visual analytics for autonomous experimentation** (live monitoring, not
   auditable replay): VISION (MLST 2025), Olympus (MLST 2021), the ALS/PETRA III
   SAXS framework (2026), Tsuchinoko, ChemOS 2.0, A-Lab (Nature 2023), Bluesky
   live callbacks. Forward-streaming score/posterior fields, convergence lines,
   live plots; none offers a scrubbable post-hoc audit, per-iteration verdicts,
   or a fidelity check. (Tsuchinoko's "Replay" is non-scrubbable re-execution.)

Foundational framing to anchor on: prospective vs retrospective provenance (Lim
et al., IEEE SCC 2010). We operationalize the retrospective side as a replayable
fold.
