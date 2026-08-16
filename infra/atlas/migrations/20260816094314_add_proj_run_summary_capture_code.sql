-- Slice 13: surface the capture code a witnessed Run's genesis already
-- stamps onto RunStarted.external_refs (Identifier(scheme="capture-code")),
-- so list_runs can filter/join on it without folding the Run stream.
-- Nullable: Conducted runs (and, defensively, a Witnessed row whose
-- genesis somehow lacked the ref) have none. Sourced from an event the
-- RunSummaryProjection already subscribes to (RunStarted); no new
-- subscription, so the projection-metadata frozenset is unaffected.

ALTER TABLE proj_run_summary ADD COLUMN capture_code text;
