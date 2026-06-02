# Standards

*ISA lenses, recipe ladder, in-code map.*

Shared vocabulary with the field, not a constraint on implementation. CORA borrows two kinds of things from standards: names (so a facility engineer recognises the model on first contact) and protocols (so clients and edges interoperate). The standards lend the shape; the implementation stays CORA's.

## Vocabulary lenses

Borrowed names and structure, not wire formats. A reader fluent in any of these should recognise the corresponding part of the code.

| Standard | Provides | Lands in |
| --- | --- | --- |
| ISA-95 | asset hierarchy (Enterprise / Site / Area / Unit / Component / Device) | `equipment` |
| ISA-88 | episodic procedures (recipe ladder: Method / Practice / Plan / Run) | `recipe`, `run` |
| ISA-106 | continuous operations | `operation`, `supply` (planned) |
| ISA-99 / IEC 62443 | trust topology (Zones, Conduits, Surfaces, Policies) | `trust` |
| ISO/IEC 42001 + NIST AI RMF | AI governance frameworks | `decision`, `agent`, `strategy` (planned) |
| W3C PROV-O | provenance vocabulary (Activity, Entity, Agent, used, wasGeneratedBy) | outbound API payloads |
| W3C SOSA / SSN | observation vocabulary (sampling procedure, observed property) | `run` (RunReading) |
| ANSI Z535.6 + EEMUA 191 | severity tiers and quotas for operator warnings | `caution` |
| RAiD (ISO 23527) | research activity identifier | `RunStarted` (forward-compat field) |

PROV-O is treated as frozen 2013 bedrock vocabulary; the W3C Provenance Working Group is closed and the spec is not moving.

## Wire and protocol standards

Implemented on the wire or conformed to as a behavioural contract. Clients and security reviewers can rely on these.

| Standard | Provides | Lands in |
| --- | --- | --- |
| OAuth 2.0 + RFC 6750 + RFC 7662 + RFC 9068 + RFC 9728 | bearer-token edge auth (BearerAuthMiddleware, JWT / introspection verifiers, protected-resource metadata) | `infrastructure/auth` |
| IETF `Idempotency-Key` (draft-07) | client-side retry safety on create-style commands | `infrastructure/idempotency` |
| IETF RFC 7396 | JSON Merge Patch semantics for partial updates | `equipment` (Asset.settings) |
| OWASP LLM Top 10 | LLM-specific threat model (prompt injection, untrusted output handling) | `agent`, `decision` |

## Recipe ladder

Michael Polanyi's observation that "we know more than we can tell" is the operating reality of every beamline. Operators carry years of practice that never makes it into the standard operating procedure (SOP), which is why software modeling only the SOP fails on contact with the floor. The ladder gives that tacit layer four steps. A **Method** is a reusable template, the portion that fits on paper. A **Practice** binds it to a site, capturing the local know-how that makes the Method operable. A **Plan** binds a Practice to specific assets and a window. A **Run** executes a Plan with a lifecycle FSM, recording the gap between plan and reality where the tacit layer becomes visible. Site-specific behaviour lives at Practice and Plan; Methods stay portable.

## On the horizon

Standards already shaping internal designs but not yet landed in shipped code. Listed here so a reader who knows them recognises the direction.

- **AAS Capability Submodel (IDTA 02020), OPC UA DI / LADS**: driver and equipment-integration vocabulary; will land alongside the first multi-vendor integration.
- **JWS-detached + DSSE PAE + Sigstore + SCITT**: signed-event vocabulary for AI-agent decisions; design locked, implementation pending.
- **EPICS V4 Normative Types**: wire vocabulary for Asset ports.
- **EPCIS 5-W invariant**: advisory check on event payloads (Who / What / When / Where / Why).
- **PIDINST profile and DataCite Instrument resourceType**: Asset persistent identifiers for external citation. CORA reserves the capacity on `equipment` Assets and decides the minting profile when the first Asset needs to be cited externally. See [Deferred](../stack/deferred.md).

## In code

For where each lens lands in the repo (BCs, aggregates, slices, ports, kernel, fitness tests), see [Reference/Layout](../reference/layout.md).
