-- 0007_phase_balance.sql
-- PHASE_BALANCE v0.1: circuits.phase + panel_phase_balance (MVP-BAL).
-- Idempotent: CREATE TABLE IF NOT EXISTS; ADD COLUMN is not idempotent in SQLite
-- (migration relies on schema_migrations to run once).

PRAGMA foreign_keys = ON;

-- circuits.phase: L1/L2/L3 for 1PH circuits (NULL allowed for 3PH or unassigned)
-- SQLite ADD COLUMN supports CHECK; existing rows are not validated.
ALTER TABLE circuits ADD COLUMN phase TEXT NULL CHECK (phase IN ('L1','L2','L3'));

-- panel_phase_balance: aggregated currents per phase + unbalance_pct
CREATE TABLE IF NOT EXISTS panel_phase_balance (
  panel_id TEXT NOT NULL REFERENCES panels(id) ON DELETE CASCADE,
  mode TEXT NOT NULL CHECK(mode IN ('NORMAL','EMERGENCY')),
  i_l1 REAL NOT NULL,
  i_l2 REAL NOT NULL,
  i_l3 REAL NOT NULL,
  unbalance_pct REAL NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(panel_id, mode)
);

CREATE INDEX IF NOT EXISTS idx_panel_phase_balance_panel_id ON panel_phase_balance(panel_id);
CREATE INDEX IF NOT EXISTS idx_panel_phase_balance_mode ON panel_phase_balance(mode);
