-- 0008_phase_source.sql
-- MVP-BAL v0.1.1: phase_source to protect MANUAL phase assignments.
-- Idempotent: ADD COLUMN is not idempotent in SQLite
-- (migration relies on schema_migrations to run once).

PRAGMA foreign_keys = ON;

-- circuits.phase_source: AUTO = algorithm-assigned; MANUAL = user-assigned (protected)
ALTER TABLE circuits ADD COLUMN phase_source TEXT NOT NULL DEFAULT 'AUTO' CHECK (phase_source IN ('AUTO','MANUAL'));
