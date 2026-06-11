-- Recipe BC: add suggested_role_ids column to Capability summary projection
-- (Layer 3 sub-slice 3E of [[project-role-aggregate-design]]).
--
-- Editorial set of global Role contract ids an operator suggests
-- this Capability is naturally satisfied by. Documentation-only per
-- memo Lock 10: NOT fitness-enforced; Methods whose capability_id
-- points here are NOT required to declare role_kind requirements
-- drawn from this set. Rule-of-three trigger fires the future
-- Capability.required_roles enforcement (deferred to Layer 4).
--
-- ## What this migration does
--
-- Adds `suggested_role_ids UUID[] NOT NULL DEFAULT ARRAY[]::UUID[]` so
-- existing Capability rows default to the empty set. The projection
-- writer maintains the column via `CapabilitySuggestedRolesUpdated`
-- wholesale-replace (Pattern P; set-edit semantic, NOT add/remove
-- pair like Family.presents_as).
--
-- Pre-pilot: zero registered Capability rows carry suggested_role_ids
-- data today; the column lights up as operators run the post-deploy
-- ceremony to populate the 5 shipped Capabilities (per Q4 user pick
-- 2026-06-10: ship MECHANISM ONLY, no inline catalog populate in
-- this commit).

ALTER TABLE proj_recipe_capability_summary
    ADD COLUMN suggested_role_ids UUID[] NOT NULL DEFAULT ARRAY[]::UUID[];

COMMENT ON COLUMN proj_recipe_capability_summary.suggested_role_ids IS
    'Editorial set of Role contract ids an operator suggests this Capability is naturally satisfied by (Layer 3 sub-slice 3E; documentation-only per memo Lock 10). Wholesale-replace via update_capability_suggested_roles.';
