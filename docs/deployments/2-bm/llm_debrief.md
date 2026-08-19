# LLM debrief comparison

*Arming 2-BM's two extra RunDebriefer serving routes for the buy-vs-build comparison: Claude Haiku 4.5 bought through
Argonne's Argo gateway, and an open model built and served in-house on facility GPUs. Both routes debit one
source-agnostic [Allocation](../../architecture/modules/budget/index.md) envelope, at the catalog's price for
whichever entry served the call.*

This page covers the whole ceremony: the catalog entries, one Agent per arm, the serving settings, the spend
envelope, and running the comparison itself.

Read [One Agent per arm](#one-agent-per-arm) before setting `LLM_PROVIDER`. The model a debrief serves comes from
the **Agent's** declared `model_ref`, not from `LLM_PROVIDER`, and the two have to agree or every call is refused.

## Catalog entries

Two [LanguageModel](../../architecture/modules/agent/index.md) entries are seeded at every boot (idempotent, harmless
on deployments that never use them), alongside the shipped fleet's three defaults:

| Name | `provider` / `model` | Served via | Cost basis | Archivability |
| --- | --- | --- | --- | --- |
| `Claude Haiku 4.5 (Argo)` | `argo` / `claude-haiku-4-5` | `Argo` | Token-priced, mirrors the direct Anthropic row | `Alias` (Argo reports the served snapshot; it cannot be requested) |
| `2-BM In-House Model (GPU Pool)` | `local` / `2bm-inhouse` | `InHouse` | Token-priced, all-zero (metered-free) | `Alias` (retarget-friendly; see below) |

Both are born `Defined` and `Approved` in the same boot-time append that seeds the shipped fleet
(`cora.agent.seed_language_models`), so `define_agent` accepts an Agent declaring either one without further
action. Confirm they exist by grepping the boot log for
`language_model_seed.created` (first boot) or `language_model_seed.already_present` (every boot after) with
`provider=argo` or `provider=local`, or by querying the read model directly:

```sql
SELECT provider, model, served_via, status
FROM proj_agent_language_model_summary
WHERE (provider, model) IN (('argo', 'claude-haiku-4-5'), ('local', '2bm-inhouse'));
```

Both rows must read `status = 'Approved'` before the settings below can do anything useful.

The in-house entry's `model` field, `2bm-inhouse`, is a stable governance identifier, not the checkpoint that
actually gets served: `LocalLLM` sends whatever `LOCAL_LLM_MODEL` names on the wire regardless of this string.
Retargeting the GPU box to a different open model is a `LOCAL_LLM_MODEL` change, not a new catalog entry.

## One Agent per arm

The catalog entries above say a model is *approved*. They do not make anything *use* it. What a debrief serves is
the declared `model_ref` of the Agent performing it, so each arm needs its own Agent declaring that arm's entry.

These are **not** seeded. An Agent is a principal, and shipping two extra principals to every CORA deployment
worldwide for one beamline's comparison would be wrong. Defining them by hand is also the better path, because
`POST /agents` applies the catalog gate for real: an Agent declaring a `(provider, model)` with no Approved entry
is refused at definition time, which is exactly the governance this comparison is meant to demonstrate.

```
POST /agents
{
  "kind": "RunDebriefer",
  "name": "ArgoRunDebriefer",
  "version": "1.0.0",
  "model_ref": {"provider": "argo", "model": "claude-haiku-4-5"},
  "description": "Buy-side arm of the 2-BM buy-vs-build debrief comparison."
}
```

```
POST /agents
{
  "kind": "RunDebriefer",
  "name": "InHouseRunDebriefer",
  "version": "1.0.0",
  "model_ref": {"provider": "local", "model": "2bm-inhouse"},
  "description": "Build-side arm of the 2-BM buy-vs-build debrief comparison."
}
```

Keep both `agent_id` values. They are what selects an arm when re-debriefing, and there is no discovery query for
them yet. `kind` must be `RunDebriefer` on both: `regenerate_run_debrief` refuses any other kind rather than
attributing a RunDebrief-context Decision to an agent that does not debrief.

## Settings, in this order

Nothing below takes effect until the process restarts: `LLM_PROVIDER` and the provider-specific settings are read
once at boot (`cora.agent.build_llm.build_llm`), not hot-reloaded.

1. **`LLM_ENABLED=true`**: the master switch. Off (the default) means no model runs on any route, regardless of
   what else is set.
2. **`LLM_PROVIDER=argo`** or **`LLM_PROVIDER=local`**: one adapter per process. The two arms of the comparison are
   two separate passes over the corpus with a config change and restart between them, not two routes live at once;
   `kernel.llm` is a single bound adapter.

    !!! warning "The live subscriber defers while an arm is armed"

        `LLM_PROVIDER` binds one adapter for the whole process, and the automatic RunDebriefer subscriber uses the
        **seeded singleton** Agent, which declares `anthropic`. With `LLM_PROVIDER=argo` or `local`, that
        singleton's declared provider no longer matches the bound adapter, the adapter refuses the call, and every
        newly completed Run debriefs to `DebriefDeferred` until the setting is put back.

        The refusal is deliberate: cost resolves from the Agent's declared `(provider, model)` while the route
        comes from configuration, so serving a call through one and pricing it as the other would silently
        misattribute spend. Failing loudly is the better trade.

        Practically: run the comparison in a no-beam window, when no Runs are completing. If beam is live, either
        accept deferred automatic debriefs for the duration, or do not arm an alternate provider at all.
3. Provider-specific settings, matching the `LLM_PROVIDER` chosen in step 2:

   **Argo arm:**
   - `ARGO_USERNAME=<username>`: the ANL domain username Argo authenticates against (not the `@anl.gov` address;
     `ac.*` accounts are rejected). **This has to name a real person's account.** Argo does not support service
     account authentication as of 2026-08, so the gateway's audit trail for every call this deployment makes points
     at whoever is named here. Treat it like an on-call rotation credential, not a durable system identity: when
     that person leaves the project or the beamline, `ARGO_USERNAME` must be reassigned to their replacement and
     the process restarted before the Argo arm is trusted again. There is no fallback that keeps working
     unattended.
   - `ARGO_BASE_URL`: leave at its default (`https://apps.inside.anl.gov/argoapi`) unless ANL moves the gateway.

   **In-house arm:**
   - `LOCAL_LLM_BASE_URL`: the served endpoint (a vLLM, Ollama, or llama.cpp host exposing the OpenAI-compatible
     `/v1/chat/completions` shape).
   - `LOCAL_LLM_MODEL`: the served checkpoint's name on that endpoint. Free to change independently of the catalog
     entry above.
   - `LOCAL_LLM_GPU_USD_PER_HOUR`: optional shadow-cost visibility (0 by default). This never debits the
     Allocation envelope; in-house serving is metered-free by design, and what debits the envelope is the catalog
     entry's token rate (zero, for this entry).
   - `LOCAL_LLM_DEVICE_ID`: labels the served device in the GPU occupancy meter (default `gpu0`).

## Grant and activate the envelope

An Allocation envelope is an operator ceremony, granted and activated through the existing budget commands
(`POST /allocations` then `POST /allocations/{id}/activate`), the same path any allocation is created through.
There is no seed for this step: the ceiling is a deliberate per-deployment decision, not a boot-time constant.

Only one Allocation may be `Active` for this deployment at a time (`activate_allocation` refuses a second one). If
2-BM already has an Active envelope for other spend, raise its ceiling with `update_allocation_ceiling` instead of
granting a new one; do not activate a second envelope alongside it.

```
POST /allocations
Idempotency-Key: <any-unique-string>   # optional but recommended
{
  "ceiling_usd": 100.00,
  "note": "Buy-vs-build LLM debrief comparison (JSR paper); SYNTHETIC ceiling, not a funded figure"
}
```

`ceiling_usd: 100.00` is a synthetic administrative figure, not a real funding award. It is not derivable from any
existing 2-BM or APS deployment doc, so it was picked with headroom rather than measured: 148 completed Runs
debriefed under both arms is at most 296 calls, and the per-call cost ceiling for Haiku-class pricing on the
`RunDebrief` prompt shape (short cached system prompt, small per-Run payload, 1024-token max output) comes out
to roughly a cent or less per call even priced pessimistically, so $100.00 leaves roughly an order of magnitude of
margin for retries and re-runs. Replace it with a real figure, or drop it via `update_allocation_ceiling`, before
this envelope is treated as a production budget rather than a paper's synthetic one.

The response carries `allocation_id`. Activate it:

```
POST /allocations/{allocation_id}/activate
```

## Verify before real Runs are touched

- **Envelope active, at the ceiling you expect:**

  ```sql
  SELECT allocation_id, ceiling_usd, status, note
  FROM proj_budget_allocation_summary
  WHERE status = 'Active';
  ```

  Exactly one row, `ceiling_usd = 100.00` (or whatever you set), and the note above.

- **Catalog entries Approved:** the query in [Catalog entries](#catalog-entries) above.

- **No unwired-LLM warning at boot.** `cora.agent.build_llm.llm_unwired_reason` is the single source every surface
  (subscriber registration, REST 503, MCP tool error) uses to say why `kernel.llm` is `None`. If it fires, the
  message names exactly which setting from the list above is still missing; there is nothing else to check.

- **One real debrief, end to end.** The three checks above are all configuration; none of them proves a call
  succeeds. Re-debrief a single Run under the arm's Agent and read back what was recorded:

  ```
  POST /agents/run-debriefer/runs/{run_id}/regenerate-debrief
  { "agent_id": "<the arm's agent_id>" }
  ```

  ```sql
  SELECT d.decided_by, i.provider_name, i.request_model, i.cost_usd
  FROM proj_decision_summary d
  JOIN inference_entries i ON i.decision_id = d.decision_id
  WHERE d.decision_id = '<returned decision_id>';
  ```

  `decided_by` must be the arm's `agent_id`, and `provider_name` must be that arm's provider. A `choice` of
  `DebriefDeferred` means the call failed, not that the model was uncertain; the deferral reason is in the
  Decision's `inputs`.

Do not point the corpus at an arm until all four checks are green. The first three can pass while the arm cannot
serve a single call, which is precisely what the fourth catches.

## Running the comparison

With both Agents defined and one arm armed, re-debrief the same Run under each. `agent_id` selects which
RunDebriefer performs it, and the model served is that Agent's own declared `model_ref`:

```
POST /agents/run-debriefer/runs/{run_id}/regenerate-debrief
{ "agent_id": "<arm agent_id>", "parent_decision_id": "<the original debrief, optional>" }
```

Passing `parent_decision_id` chains the new Decision to the one it re-evaluates (a PROV-O `wasInformedBy` edge),
which is what lets a reader see that two verdicts concern the same Run rather than two unrelated ones.

Because one process binds one adapter, the corpus is walked twice: arm the first provider, walk it, change
`LLM_PROVIDER`, restart, walk it again with the other Agent. Both passes debit the same envelope, at each entry's
catalog rate, which is the property this comparison exists to demonstrate.
