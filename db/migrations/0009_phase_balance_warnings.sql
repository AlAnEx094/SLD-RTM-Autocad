-- 0009_phase_balance_warnings.sql
-- MVP-BAL v0.1.2: warnings for MANUAL circuits with invalid phase.
-- Idempotent: ADD COLUMN is not idempotent in SQLite
-- (migration relies on schema_migrations to run once).

PRAGMA foreign_keys = ON;

-- panel_phase_balance: count of MANUAL circuits with invalid phase (e.g. 3PH with phase set)
ALTER TABLE panel_phase_balance ADD COLUMN invalid_manual_count INT NOT NULL DEFAULT 0;

-- panel_phase_balance: JSON array of warning messages (DB-backed warnings)
ALTER TABLE panel_phase_balance ADD COLUMN warnings_json TEXT NULL;
