-- Seed the In-process Surface: the arrival door for CORA's own in-process
-- work (agent tick loops, capture readers, one-time operator
-- entrypoints) that calls a handler directly, with no HTTP request or
-- MCP tool call behind it. Atomic via Atlas's per-file outer transaction
-- (default txmode=file; every other migration in this repo relies on
-- it, no inner BEGIN/COMMIT: that would either error "transaction in
-- progress" or break atomicity by committing mid-file). Re-run
-- idempotency comes from ON CONFLICT DO NOTHING.
--
-- Before this seed, every in-process handler call omitted `surface_id`
-- entirely and fell through to `NIL_SENTINEL_ID` ("unspecified"),
-- indistinguishable from any other caller a Policy has not yet
-- classified. This Surface gives that internal work a real, nameable
-- door: a Policy can now permit or deny CORA's own background work
-- differently from a person clicking a button, something the nil
-- sentinel could never express since it strict-matches against
-- whatever a policy happens to be bound to.
--
-- A single genesis event is enough: unlike Conduit, Surface carries no
-- logbook, so there is nothing else to open on this stream.
--
-- Seeds:
--   - SYSTEM_IN_PROCESS_SURFACE_ID = ...0023 (kind=in_process)
--
-- Constants live in cora.infrastructure.routing, re-exported from
-- cora.trust._bootstrap. Continues the ...0020 / ...0021 / ...0022
-- sequence seeded by 20260519200000_seed_default_surfaces_and_v2_policy.sql.

INSERT INTO events (
    event_id, stream_type, stream_id, version, event_type,
    payload, metadata, correlation_id, principal_id, occurred_at
) VALUES (
    gen_random_uuid(), 'Surface',
    '00000000-0000-0000-0000-000000000023'::uuid, 1, 'SurfaceDefined',
    jsonb_build_object(
        'surface_id',  '00000000-0000-0000-0000-000000000023',
        'name',        'System In-process',
        'kind',        'in_process',
        'occurred_at', '2026-08-31T15:00:00+00:00'
    ),
    jsonb_build_object('command', 'SystemBootstrap'),
    '00000000-0000-0000-0000-000000000000'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    '2026-08-31 15:00:00+00'::timestamptz
)
ON CONFLICT (stream_type, stream_id, version) DO NOTHING;
