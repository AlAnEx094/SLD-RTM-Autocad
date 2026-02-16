-- 0006_section_calc_mode_emergency.sql
-- section_calc: change mode from NORMAL/RESERVE to NORMAL/EMERGENCY.
-- SQLite cannot ALTER CHECK; rebuild table with best-effort data migration.

PRAGMA foreign_keys = ON;

-- Create new table with v2 mode constraint (NORMAL, EMERGENCY)
CREATE TABLE IF NOT EXISTS section_calc_new (
  panel_id TEXT NOT NULL REFERENCES panels(id) ON DELETE CASCADE,
  bus_section_id TEXT NOT NULL REFERENCES bus_sections(id) ON DELETE CASCADE,
  mode TEXT NOT NULL CHECK(mode IN ('NORMAL', 'EMERGENCY')),
  p_kw REAL NOT NULL,
  q_kvar REAL NOT NULL,
  s_kva REAL NOT NULL,
  i_a REAL NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(panel_id, bus_section_id, mode)
);

-- Copy data: map RESERVE -> EMERGENCY, NORMAL stays NORMAL
INSERT INTO section_calc_new (panel_id, bus_section_id, mode, p_kw, q_kvar, s_kva, i_a, updated_at)
SELECT
  panel_id,
  bus_section_id,
  CASE WHEN mode = 'RESERVE' THEN 'EMERGENCY' ELSE mode END,
  p_kw,
  q_kvar,
  s_kva,
  i_a,
  updated_at
FROM section_calc;

-- Replace old table
DROP TABLE section_calc;
ALTER TABLE section_calc_new RENAME TO section_calc;

-- Recreate indexes
CREATE INDEX IF NOT EXISTS idx_section_calc_panel_id ON section_calc(panel_id);
CREATE INDEX IF NOT EXISTS idx_section_calc_bus_section_id ON section_calc(bus_section_id);
CREATE INDEX IF NOT EXISTS idx_section_calc_mode ON section_calc(mode);
