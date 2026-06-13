# Backend

For implementers picking the server-side runtime. Each row names a role, the current pick, the reason, and the trigger that would force a swap.

## Language and runtime

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| Language | Python 3.13 | Pyright strict, structural typing, async-first, scientific ecosystem | Embedded controls path may move to Rust; core stays Python |
| HTTP server | Uvicorn | Standard async ASGI; integrates with FastAPI | Hypercorn if HTTP/2 or H/3 becomes a hard requirement |

## HTTP and schemas

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| HTTP framework | FastAPI | Pydantic v2 schemas, OpenAPI for free, mature async | Successor with same Pydantic + async story (Litestar) |
| Validation | Pydantic v2 | De facto FastAPI schema standard | Coupled to HTTP framework |
| Settings | pydantic-settings | Env-var `Settings` class with Pydantic validation | Coupled to Validation |
| Runtime JSON Schema | jsonschema-rs | Rust-backed validator for schema-validated values (Capability / Method / Asset settings) at request time; distinct from Pydantic, which validates the HTTP envelope | Validator semantics or Draft support outgrowing the Rust binding |

## Persistence

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| Async DB driver | asyncpg | Lowest-overhead Postgres driver; needed for projection throughput | Workload asyncpg's API can't accommodate |
| ID generation | uuid-utils (UUIDv7) | Backs `IdGenerator` port; time-ordered keys without exposing wall-clock | PG18's native `uuidv7()` rejected per non-determinism principle |

## Agent protocol

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| Agent-protocol SDK | `mcp` (official Python SDK) | First-party, tracks the spec | Major MCP-spec break |

## AI and agents

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| LLM provider | Anthropic via the `anthropic` SDK | Backs the `LLM` port through the `AnthropicLLM` adapter; powers the RunDebriefer and CautionDrafter subscribers (reasoning generation is shipped). Subscribers, deciders, and tests use the port + `FakeLLM`, never the SDK | Provider change; a future `OpenAILLM` / local-model adapter slots behind the same port without subscriber changes |

## Control and actuation

The `ControlPort` behind the Operation BC speaks EPICS. Production reads and writes go through the asyncio EPICS clients; tests drive a real softIOC subprocess rather than the production clients.

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| EPICS Channel Access | aioca | Production asyncio CA client behind `EpicsCaControlPort`; Diamond Light Source-maintained | CA workload outgrowing the client |
| EPICS pvAccess | p4p | Production asyncio PVA client behind `EpicsPvaControlPort`; carries Normative Types (NTNDArray image streams CA cannot) | PVA workload outgrowing the client |
| EPICS test IOC | caproto + epicscorelibs | Test-only: `epicscorelibs.ioc` spawns a real softIOC subprocess; caproto backs the test-only `CaprotoControlPort`. caproto's own README warns against production use | Stays test-only; production CA/PVA go through aioca / p4p |

## Signing

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| Event / byte signing | cryptography (Ed25519) | Backs the `Signer` port; the in-memory adapter produces and verifies raw 64-byte Ed25519 signatures over PAE-wrapped canonical body bytes | Production swaps in a KMS / Sigstore / SPIFFE backend behind the same port |
