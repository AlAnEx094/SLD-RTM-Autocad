-- 0002_circuits.sql
-- MVP-0.2: Схема для цепей расчёта ΔU.

PRAGMA foreign_keys = ON;

-- Расширение щитов: лимиты ΔU и тип монтажа
ALTER TABLE panels ADD COLUMN du_limit_lighting_pct REAL NOT NULL DEFAULT 3.0;
ALTER TABLE panels ADD COLUMN du_limit_other_pct REAL NOT NULL DEFAULT 5.0;
ALTER TABLE panels ADD COLUMN installation_type TEXT DEFAULT 'A';

-- Цепи (линии)
CREATE TABLE IF NOT EXISTS circuits (
  id TEXT PRIMARY KEY,
  panel_id TEXT NOT NULL,
  name TEXT,
  phases INTEGER NOT NULL CHECK (phases IN (1, 3)),
  neutral_present INTEGER NOT NULL DEFAULT 1,
  unbalance_mode TEXT NOT NULL DEFAULT 'NORMAL' CHECK (unbalance_mode IN ('NORMAL', 'FULL_UNBALANCED')),
  length_m REAL NOT NULL,
  material TEXT NOT NULL CHECK (material IN ('CU', 'AL')),
  cos_phi REAL NOT NULL,
  load_kind TEXT NOT NULL DEFAULT 'OTHER' CHECK (load_kind IN ('LIGHTING', 'OTHER')),
  i_calc_a REAL NOT NULL,
  FOREIGN KEY(panel_id) REFERENCES panels(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_circuits_panel_id ON circuits(panel_id);

-- Стандартные сечения кабеля
CREATE TABLE IF NOT EXISTS cable_sections (
  s_mm2 REAL PRIMARY KEY
);

-- Расчёт цепей по ΔU
CREATE TABLE IF NOT EXISTS circuit_calc (
  circuit_id TEXT PRIMARY KEY,
  i_calc_a REAL NOT NULL,
  du_v REAL NOT NULL,
  du_pct REAL NOT NULL,
  du_limit_pct REAL NOT NULL,
  s_mm2_selected REAL NOT NULL,
  method TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(circuit_id) REFERENCES circuits(id) ON DELETE CASCADE
);
