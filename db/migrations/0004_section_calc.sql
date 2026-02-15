-- 0004_section_calc.sql
-- MVP-0.3: Расчёт по секциям шин (агрегация потребителей/вводов).

PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS section_calc (
  panel_id TEXT NOT NULL REFERENCES panels(id) ON DELETE CASCADE,
  bus_section_id TEXT NOT NULL REFERENCES bus_sections(id) ON DELETE CASCADE,
  mode TEXT NOT NULL CHECK(mode IN ('NORMAL','RESERVE')),
  p_kw REAL NOT NULL,
  q_kvar REAL NOT NULL,
  s_kva REAL NOT NULL,
  i_a REAL NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(panel_id, bus_section_id, mode)
);

CREATE INDEX IF NOT EXISTS idx_section_calc_panel_id ON section_calc(panel_id);
CREATE INDEX IF NOT EXISTS idx_section_calc_bus_section_id ON section_calc(bus_section_id);
CREATE INDEX IF NOT EXISTS idx_section_calc_mode ON section_calc(mode);

