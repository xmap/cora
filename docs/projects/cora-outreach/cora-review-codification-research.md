# Review-Process Codification: Should CORA Commit the Loop?

A corpus-grounded decision framework on whether the multi-axis pre-push review should live as durable artifacts (subagents, hooks, ledger) or stay with the operator and the model in the moment.

## 1. One-Paragraph Answer

The corpus splits cleanly into two camps that agree on the gradient but disagree on the extrapolation: free-form voices (Cherny, Karpathy, Willison) bet that the next model erases today's scaffolding, while codification voices (Boeckeler, Yan, Anthropic's own best-practices page) bet that long-lived correctness demands explicit anchors. The practitioner consensus is narrower than either extreme: codify the *knowledge* and the *invariants*, free-form the *loop that invokes them*; ten of ten solo OSS projects surveyed commit a thin PR template and a CONTRIBUTING file, three of ten (Astral ruff, Astral uv, Bun) commit `AGENTS.md` operational playbooks, and zero of ten commit a multi-axis reviewer pipeline or a per-PR ledger. CORA's situation (16 BCs, 28 aggregates, 53+ design memos, a single operator, a 5-year horizon, MEMORY.md already over its size warning, and a documented near-miss on the R3 noun-LAST rule) puts it on the codification side of the gradient for reviewer *prompts* but on the free-form side for reviewer *orchestration*. Recommendation framed as a conditional: if you have already paid the rule-of-three for a given review axis (R3 naming, BC-boundaries, plan-conformance), then commit that axis as a `.claude/agents/<axis>.md` subagent file and reference it from `CLAUDE.md`; if you have not, do not pre-build the pipeline, the ledger, or the gating hooks, because every codified-tool failure mode in the corpus (rule rot, ritual bypass, harness debt) hits solo devs HARDER than enterprises and the asymmetric downside favors the lighter artifact.

## 2. Corpus Headlines

- **Anthropic's own load-bearing test:** "Would removing this cause Claude to make mistakes? If not, cut it." Hooks for deterministic gates, skills for on-demand knowledge, subagents for fresh-context review. [Best practices for Claude Code](https://code.claude.com/docs/en/best-practices)
- **Boeckeler on anchor-rot:** prose-only standards are "Java exams at university, in pencil" because no compiler catches decay; a living reference application is the antidote. [Anchoring AI to a Reference Application](https://martinfowler.com/articles/exploring-gen-ai/anchoring-to-reference.html)
- **Boeckeler on context overload:** "the agent's effectiveness goes down when it gets too much context"; teams "inadvertently repeat instructions or contradict existing ones." [Context Engineering for Coding Agents](https://martinfowler.com/articles/exploring-gen-ai/context-engineering-coding-agents.html)
- **Cherny's bitter-lesson bet:** "everything is the model; as the model gets better, it subsumes everything else"; CLAUDE.md is "the simplest thing that could work." [Latent Space Claude Code episode](https://www.latent.space/p/claude-code)
- **Solo OSS minimum pattern:** ten of ten projects ship CONTRIBUTING + thin PR template; three of ten (Astral ruff, Astral uv, Bun) commit `AGENTS.md` operational playbooks; zero commit reviewer-side checklists or multi-axis pipelines. [Ruff AGENTS.md](https://github.com/astral-sh/ruff/blob/main/AGENTS.md), [Bun AGENTS.md](https://github.com/oven-sh/bun/blob/main/AGENTS.md)
- **GitClear churn signal:** code reverted within two weeks forecast to double vs 2021 baseline under heavy Copilot use; review caught syntax but not duplication-and-discard. [GitClear study](https://www.gitclear.com/coding_on_copilot_data_shows_ais_downward_pressure_on_code_quality)
- **Solo-dev sustainability of artifacts (tools survey):** highest-rated are pre-commit (10/10), Reviewdog (9/10), Semgrep (9/10), ArchUnit (9/10), all repo-local; lowest are SaaS-interpreted YAML (CodeRabbit 4/10, Snyk 5/10) because the verdict lives off-checkout. [pre-commit](https://pre-commit.com), [Semgrep](https://semgrep.dev/docs/writing-rules/rule-syntax)
- **No published convention for axis-decomposed AI review:** the Claude community has shipped role-per-language reviewers (wshobson) and Anthropic's two-reviewer pattern (correctness + plan-conformance), but nobody publishes the multi-axis matrix CORA is sketching. [wshobson/agents](https://github.com/wshobson/agents)

## 3. Codification Continuum Table

Eight gaps from the prior audit, numbered for reference:
1. persistent reviewer prompts across sessions
2. per-PR review ledger
3. axis disclosure (which review dimensions exist)
4. verification record (what was checked)
5. inconsistent review depth
6. missing security pass
7. operator-change survival (handoff)
8. over-engineering (codification itself)

| Tier | Who uses it | Gaps closed | Maintenance | Failure mode | Solo fit |
|---|---|---|---|---|---|
| **T0: Nothing committed** | Karpathy vibe-coding, throwaway scope | None | Zero | Anchor-rot, convention drift, poisoned context | 3/10 for 5-yr horizon |
| **T1: PR template only** | htmx, Tailwind, Starlette, httpx, FastAPI, Pydantic, Rails | 3 (axis disclosure via checklist), partial 7 | Near zero; edit when norms change | Checklist becomes ritual; reviewer-of-one acks-all | 9/10 |
| **T2: PR template + CLAUDE.md + bundled skills (`/code-review`, `/security-review`)** | CORA today; Anthropic best-practices baseline; Willison ("codify knowledge, free-form loop") | 3, 6, partial 1, partial 7 | Low; CLAUDE.md edits track convention shifts | Reviewer-fatigue ("a reviewer prompted to find gaps will usually report some") | 9/10 |
| **T3: Committed `AGENTS.md` + reviewer subagents in `.claude/agents/`** | Astral ruff, Astral uv, Bun, wshobson marketplace | 1, 3, 6, 7, partial 5 | Medium; quarterly prune per Boeckeler | Rule rot if not pruned; copy-paste accretion | 7/10 |
| **T4: Committed workflow + hooks + JSON ledger** | No surveyed solo project; Anthropic enterprise teams via plugins | 1, 2, 3, 4, 5, 6, 7 | High; harness IS code, harness has debt | Harness maintenance debt (OpenAI 5-month build with GC agents fighting decay); ritual bypass (Kiro's 16 acceptance criteria for a bug fix) | 4/10 |
| **T5: External SaaS bot (CodeRabbit, Sourcery, Snyk policies)** | Enterprise teams with CI budget | 1, 2, 4, 6 (vendor-mediated) | Vendor absorbs; you absorb config drift | Verdict not reproducible from checkout; vendor pricing changes; review-summary balloon | 4/10 |

Notes the corpus is silent on: nobody publishes a controlled comparison of T2 vs T3 outcomes for solo devs over multi-year horizons; the failure-story bank skews toward T4 and T5 because those generate dramatic post-mortems while T2 quietly works.

## 4. Three Steelman Positions Distilled

**Position A: Don't codify the review process.**
- The eight-failure corpus shows three over-codification failures (rule rot, ritual bypass, harness debt) that all hit solo devs HARDER than enterprises; Anthropic's own "would removing this cause mistakes? if not, cut it" test fails for most reviewer scaffolding.
- The minimum solo OSS pattern is brutally thin: htmx, Pydantic, Starlette, httpx, FastAPI, Tailwind all ship without committed reviewer checklists; the projects that DID add ceremony (Kiro spec-kit, OpenAI's 5-month harness) regret it.
- CORA's existing architecture-fitness suite plus `tracked_python_files()` plus content-addressed identity already IS the compilable anchor Boeckeler prescribes; codifying review on top of that adds ritual without adding anchor.
- The bitter-lesson bet: every reviewer file you write today is a file the next model subsumes; trust Opus 4.7 to 5.0 generalization and keep CLAUDE.md as the surface.

**Position B: Fully codify workflow + agents + PR template + ledger.**
- CORA is not a weekend project; it is 16 BCs, 28 aggregates, 53+ memos, MEMORY.md already over the size warning. The operator literally cannot remember the rules; the model cannot infer them from a poisoned context full of legacy patterns.
- The Doernenburg CCMenu failure is the closest analog: codified conventions existed in the codebase but were not load-bearing in the agent's context; the R3 noun-LAST near-miss recorded in `feedback_audit_r3_direction.md` is the rule-of-three trigger fired.
- Six of seven rubric questions (recurrence, future-non-obvious, statability, no-deploy-variance, mechanism-vs-judgment, no-silent-failure) push CORA toward codification; only Q3 (eval-verifiable) partially fails.
- ArchUnit, Semgrep, and pre-commit have survived multiple model generations precisely because they do not depend on a model; reviewer subagent files are 30 lines of markdown each, proportional in cost to churn.

**Position C: Commit the prompts, skip the pipeline.**
- The corpus's convergent practice is prompts-as-artifacts, invocation-as-judgment: Astral and Bun commit `AGENTS.md` plus subagent files but never a pipeline or ledger; wshobson's 191-agent marketplace is the same shape at scale.
- The cost curves of prompt-codification and pipeline-codification differ by an order of magnitude: a reviewer prompt is 30-200 lines of markdown editable monthly and reproducible from checkout (Semgrep/ArchUnit profile); a pipeline is code that hits every harness-debt failure in the corpus.
- The framework rubric splits the same way: reviewer prompts pass Q1/Q2/Q5 (recurred, future-non-obvious, per-stage variance), pipeline machinery fails Q1/Q4/Q7 (no recurrence, when-to-invoke is judgment, silent failure of orchestration is worse than no orchestration).
- A ledger you do not read is decoration: SQLite's release checklist (200 items, Gawande-inspired) is for releases not PRs; Hipp distrusts automation specifically for catching what tests miss; the git log IS the ledger for a solo dev.

## 5. Decision Framework

Seven questions. For each: what pushes toward more codification, what pushes toward less, what CORA's actual answer is from the auto-memory and recent commits.

**Q1. Has this review axis caught the same class of mistake three or more times?**
More codify if yes (Rule of Three, Fowler); less if speculative.
*CORA answer:* yes for naming (R3 audit, naming round-5, plurality sweep), yes for BC-boundary (update-handler factory, `_actor_update_handler` hoist), yes for plan-conformance (gate-review memo). No for security beyond bundled `/security-review`. Pushes toward T3 for those three axes specifically, not for review-in-general.

**Q2. Would the rationale be non-obvious to me in six months?**
More codify if yes (ADR pattern, letter to future self); less if reversible-and-obvious.
*CORA answer:* yes, demonstrably; 53+ design memos and a MEMORY.md overflow prove the operator already loses context across months. Pushes toward T3.

**Q3. Is the behavior verifiable by an automated check?**
More codify as eval if yes; leave as prose if not.
*CORA answer:* partly. Architecture-fitness covers structural invariants; naming R3, plan-conformance, and altitude judgments are not eval-verifiable today. Pushes toward T2/T3 hybrid: keep evals where they work, add reviewer subagents only where they cannot reach.

**Q4. Is the rule easier to state than to demonstrate with examples?**
More codify (Software 1.0) if statable; less (Software 2.0) if better-demonstrated.
*CORA answer:* mixed. R1-R4 naming rules are statable; "is this docstring at the right altitude" is demonstration-only. Pushes toward T2 for the demonstration-only axes (let the model judge with examples in context); T3 for the statable ones.

**Q5. Does this review vary per stage type (Stage-0 research vs Stage-1 design vs BC-shipping commit)?**
More codify (separate artifacts per axis) if yes; less if uniform.
*CORA answer:* yes; `feedback_gate_review_before_commit.md` already records "3 baseline + 1 specialist" varying by stage. Pushes toward T3 with one subagent per axis, invoked selectively.

**Q6. Is this mechanism (the gate) or policy (the judgment about when to gate)?**
Mechanism into pipeline; policy into operator-controlled config.
*CORA answer:* the *axes* are mechanism (stable list); the *which-to-invoke-on-this-PR* is policy (varies). Pushes toward T3 (commit the axes) but NOT T4 (do not commit the gating).

**Q7. Would a silent failure here be acceptable on the production critical path?**
No silent failure tolerated -> codify the invariant. Yes -> vibe-code.
*CORA answer:* no, demonstrably; CORA has a forward-only-migrations stance, no rollback culture for memos, single operator. Pushes toward codification UNLESS the codification itself silently fails (the harness-debt failure mode), which is the precise reason to stop at T3 and not progress to T4.

Tally: five push toward T3 (prompts as committed artifacts), two push against T4 (orchestration as code). Convergent on Position C.

## 6. Tailored Recommendation for CORA

The framework lands on **Position C with a sharp caveat**: commit the reviewer prompts as subagent files, do not build the pipeline or the ledger, and accept that invocation is operator (or auto-delegating Claude) judgment.

Showing the work. Of the four serious counterarguments:

- *"The bitter lesson will eat your scaffolding"* (Cherny, Position A): valid for capability scaffolding (compaction, memory, planning) which CORA is not building; not valid for policy scaffolding (R3 noun-LAST, BC-boundary rules) which is project-specific and will never be in the model's weights.
- *"Inconsistent enforcement is worse than absent enforcement"* (Position B's strongest shot at C): valid in principle, but the failure corpus is unambiguous that ritual bypass kills heavier systems faster than absent rituals kill lighter ones; the asymmetric downside favors the lighter artifact for solo devs.
- *"Anchor-rot will catch you"* (Boeckeler, Position B): CORA's architecture-fitness suite plus `tracked_python_files()` plus 28 aggregates of compiled invariants IS the anchor; reviewer subagents complement the anchor rather than replace it.
- *"Prompts will rot"* (Position A counter to C): yes, and so do tests; the mitigation is the same (rule-of-three before extraction, quarterly prune per Boeckeler, ADR for the why).

Where CORA's situation forces a deviation from Position C as written: the steelman C ends at four committed subagents and CLAUDE.md changes. Given the MEMORY.md overflow, the project should also rotate the new policy through a memory entry (`feedback_reviewer_invocation.md`) so it survives auto-memory pressure and so future-Doğa loads it as part of the standing user index. This is paying the existing memory-pattern tax, not adding new ceremony.

What stays explicitly out: no `.claude/workflows/` directory, no hook-based commit gating, no JSON-receipt ledger, no SaaS bot. Each of those failed at least one rubric question (Q1 for workflows, Q7 for hooks, Q3-and-Q4 for ledgers, Q7 for SaaS), and each carries a documented failure mode the solo configuration cannot absorb.

The five-year horizon point deserves naming. The bitter-lesson camp's strongest move is "in five years this is all moot." Even granting that, the cost of writing four 80-line markdown files today and pruning them quarterly is bounded; the cost of NOT writing them and continuing to lose context to MEMORY.md overflow is unbounded. The expected value comparison favors action over wait-and-see.

## 7. Minimum-Viable Next Step

The smallest reversible commit that tests the chosen direction is **one subagent file plus a CLAUDE.md cross-reference**, not four.

Concrete shape:

- Create `.claude/agents/naming-r3-reviewer.md`, ~60-100 lines, YAML frontmatter with `name: naming-r3-reviewer`, `description:` written for Claude's auto-delegation matcher (so it triggers on rename PRs without manual `/` invocation), `tools: Read, Grep, Glob, Bash`, `model: opus`. Body: the R3 noun-LAST rule, the R1/R2/R4 reads, a link to `docs/reference/conventions.md` and to the existing `project_naming_conventions.md` memory entry.
- Add to `CLAUDE.md` under a new short `## Reviewer subagents` section: one line naming the agent and its trigger ("before any rename or new-name commit, invoke `naming-r3-reviewer`").
- Do NOT add a memory entry yet; let the artifact prove its value through one or two real invocations first.

Why this is the right test: naming R3 is the axis with the strongest rule-of-three signal (audit, round-5, plurality sweep, near-miss memo), the cheapest invariant to state, and the easiest to evaluate from outcomes ("did this rename PR catch the noun-last violation that would otherwise have shipped?"). If the test succeeds, the same pattern extends to BC-boundary, plan-conformance, and altitude. If it fails (the agent is noisy, the description fails to auto-trigger, the prose rots within two months), delete the file, revert the CLAUDE.md line, and Position A wins on evidence rather than speculation.

Reversibility cost is one `git revert` of two files. Lock-in cost is zero.

## 8. Open Questions

Three points need the user's input before scaling beyond the minimum-viable step.

**Q1. Auto-delegation vs explicit invocation.** Anthropic's subagent system supports both: a well-written `description:` field lets Claude pick the reviewer automatically, while `/naming-r3-reviewer` is operator-driven. Auto-delegation reduces operator burden and matches Position C's "invocation is judgment" stance but produces reviewer-fatigue noise if the matcher fires too often; explicit invocation is sharper but relies on operator memory (the failure mode CORA is trying to mitigate). Recommend: start auto-delegating with a tight description; downgrade to explicit if noise exceeds signal in the first ten PRs.

**Q2. Where do reviewer files live for cross-BC vs BC-specific axes?** Naming R3 is universal (one file at `.claude/agents/`). But a hypothetical "Federation port shape reviewer" is BC-specific and the corpus has no convention for nested subagent directories. CORA's existing BC-root-layout memo (flat private files until ~10) suggests flat-then-nest; recommend deferring this question until a second axis with BC-specific scope earns its rule-of-three.

**Q3. Memory entry shape.** Once the minimum-viable test passes, the `feedback_reviewer_invocation.md` entry needs to fit MEMORY.md's already-tight budget. The user has historically chosen one-line index entries with detail in topic files; recommend that pattern with detail in `project_reviewer_subagents_design.md` so the auto-memory loads only the trigger condition, not the prompt prose. Confirm before authoring.

Where the corpus is silent: no published outcome data exists on solo-dev subagent maintenance burden over multi-year horizons; the Astral and Bun `AGENTS.md` files are recent enough (2024-2026) that decay evidence has not accumulated. CORA's experiment will be among the data points future projects cite.
