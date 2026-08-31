-- Seed a Zone, a Conduit, and its verdict logbook, so a deployment that
-- opts in can populate the per-decision authz audit log
-- (entries_conduit_verdicts). Atomic via Atlas's per-file outer
-- transaction (default txmode=file); no inner BEGIN/COMMIT, since that
-- would either error "transaction in progress" or break atomicity by
-- committing mid-file (see 20260519200000_seed_default_surfaces_and_v2_policy.sql's
-- header and memory/project_conduit_injection_design.md).
--
-- Watch item 6 of memory/project_authorization_envelope_design.md named
-- this fix precisely: "conduit injection + a seeded verdict logbook, NOT
-- just flipping trust_policy_id", trigger "a compliance/ops need for one
-- queryable cross-layer log". Every deployment's authorize() call passes
-- conduit_id=NIL_SENTINEL_ID (Settings.trust_conduit_id defaults to
-- None), so this seed is inert until an operator opts in — same shape
-- as trust_policy_id / TRUST_POLICY_ID.
--
-- Deployment-neutral naming ("System Local ...", not "2-BM ..."): this
-- migration ships to every deployment, not just 2-BM.
--
-- Seeds:
--   - SYSTEM_LOCAL_ZONE_ID    = ...0030 (kind: Zone, source == target)
--   - SYSTEM_LOCAL_CONDUIT_ID = ...0031 (endpoints both ...0030)
--   - verdict logbook          = ...0032 (kind='verdict', opened on the
--                                          Conduit's own stream, version 2)
--
-- Constants live in cora.infrastructure.routing, re-exported from
-- cora.trust._bootstrap. Ids are deliberately NOT the nil sentinel: a
-- real Conduit id keeps NIL_SENTINEL_ID meaning "unspecified", never
-- "this one, in particular".

-- Local Zone (both Conduit endpoints bind here; ISA-99 topology is
-- inert at v1 per project_conduit_injection_design.md WI10, so a single
-- self-loop zone is honest rather than a placeholder split).
INSERT INTO events (
    event_id, stream_type, stream_id, version, event_type,
    payload, metadata, correlation_id, principal_id, occurred_at
) VALUES (
    gen_random_uuid(), 'Zone',
    '00000000-0000-0000-0000-000000000030'::uuid, 1, 'ZoneDefined',
    jsonb_build_object(
        'zone_id',     '00000000-0000-0000-0000-000000000030',
        'name',        'System Local Zone',
        'occurred_at', '2026-08-31T14:00:00+00:00'
    ),
    jsonb_build_object('command', 'SystemBootstrap'),
    '00000000-0000-0000-0000-000000000000'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    '2026-08-31 14:00:00+00'::timestamptz
)
ON CONFLICT (stream_type, stream_id, version) DO NOTHING;

-- Local Conduit — genesis.
INSERT INTO events (
    event_id, stream_type, stream_id, version, event_type,
    payload, metadata, correlation_id, principal_id, occurred_at
) VALUES (
    gen_random_uuid(), 'Conduit',
    '00000000-0000-0000-0000-000000000031'::uuid, 1, 'ConduitDefined',
    jsonb_build_object(
        'conduit_id',      '00000000-0000-0000-0000-000000000031',
        'name',            'System Local Conduit',
        'source_zone_id',  '00000000-0000-0000-0000-000000000030',
        'target_zone_id',  '00000000-0000-0000-0000-000000000030',
        'occurred_at',     '2026-08-31T14:00:00+00:00'
    ),
    jsonb_build_object('command', 'SystemBootstrap'),
    '00000000-0000-0000-0000-000000000000'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    '2026-08-31 14:00:00+00'::timestamptz
)
ON CONFLICT (stream_type, stream_id, version) DO NOTHING;

-- Local Conduit — verdict logbook opened. Schema mirrors
-- _TRAVERSALS_SCHEMA in cora/trust/features/define_conduit/decider.py
-- exactly, so a hand-seeded Conduit's logbook declaration is
-- byte-identical to one opened through the API.
INSERT INTO events (
    event_id, stream_type, stream_id, version, event_type,
    payload, metadata, correlation_id, principal_id, occurred_at
) VALUES (
    gen_random_uuid(), 'Conduit',
    '00000000-0000-0000-0000-000000000031'::uuid, 2, 'ConduitLogbookOpened',
    jsonb_build_object(
        'conduit_id', '00000000-0000-0000-0000-000000000031',
        'logbook_id', '00000000-0000-0000-0000-000000000032',
        'kind',       'verdict',
        'schema',     jsonb_build_object(
            'fields', jsonb_build_object(
                'actor_id', jsonb_build_object(
                    'type', 'uuid',
                    'description', 'The principal that issued the command.'
                ),
                'command_name', jsonb_build_object(
                    'type', 'string',
                    'description', 'Cross-BC command name (for example ''StartRun'', ''DefinePolicy'').'
                ),
                'decision', jsonb_build_object(
                    'type', 'string',
                    'description', '''Allow'' or ''Deny'', from the Authorize port result.'
                ),
                'reason', jsonb_build_object(
                    'type', 'string',
                    'description', 'Free-form reason on Deny; null on Allow.'
                )
            ),
            'description', 'Per-decision authorization audit log for commands traversing this Conduit. One row per Authorize port call.'
        ),
        'occurred_at', '2026-08-31T14:00:00+00:00'
    ),
    jsonb_build_object('command', 'SystemBootstrap'),
    '00000000-0000-0000-0000-000000000000'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    '2026-08-31 14:00:00+00'::timestamptz
)
ON CONFLICT (stream_type, stream_id, version) DO NOTHING;
