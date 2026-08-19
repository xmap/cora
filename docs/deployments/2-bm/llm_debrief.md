# LLM debrief comparison

*Arming 2-BM's two extra RunDebriefer serving routes for the buy-vs-build comparison: Claude Haiku 4.5 bought through
Argonne's Argo gateway, and an open model built and served in-house on facility GPUs. Both routes debit one
source-agnostic [Allocation](../../architecture/modules/budget/index.md) envelope, at the catalog's price for
whichever entry served the call.*

This page covers what is armed today: the catalog entries, the serving settings, and the spend envelope. It does
not yet cover running the comparison itself, running the same completed Run's debrief a second time under the
other model, because that needs a `regenerate_run_debrief` change (letting the operator name which RunDebriefer
variant re-debriefs a Run) that has not landed. This page gains that section once it does.

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

## Settings, in this order

Nothing below takes effect until the process restarts: `LLM_PROVIDER` and the provider-specific settings are read
once at boot (`cora.agent.build_llm.build_llm`), not hot-reloaded.

1. **`LLM_ENABLED=true`**: the master switch. Off (the default) means no model runs on any route, regardless of
   what else is set.
2. **`LLM_PROVIDER=argo`** or **`LLM_PROVIDER=local`**: one adapter per process. The two arms of the comparison are
   two separate passes over the corpus with a config change and restart between them, not two routes live at once;
   `kernel.llm` is a single bound adapter.
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

Do not point real Runs at either arm until both checks above are green. The comparison itself, which Run gets
debriefed under which model, is not yet operator-selectable; that lands with the `regenerate_run_debrief` change
noted at the top of this page.
