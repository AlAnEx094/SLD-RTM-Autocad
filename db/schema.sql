-- schema.sql
-- Агрегированный слепок схемы (MVP-0.1).
-- Источник истины для эволюции схемы — миграции в db/migrations/.
--
-- На MVP-0.1 схема == db/migrations/0001_init.sql (вставлено вручную, без магии).

PRAGMA foreign_keys = ON;

-- Щиты
CREATE TABLE IF NOT EXISTS panels (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  system_type TEXT NOT NULL CHECK (system_type IN ('3PH', '1PH')),
  u_ll_v REAL,
  u_ph_v REAL
);

-- Вводные строки РТМ + параметры фазировки
CREATE TABLE IF NOT EXISTS rtm_rows (
  id TEXT PRIMARY KEY,
  panel_id TEXT NOT NULL,
  name TEXT NOT NULL,
  n INTEGER NOT NULL,
  pn_kw REAL NOT NULL,
  ki REAL NOT NULL,
  cos_phi REAL,
  tg_phi REAL,
  phases INTEGER NOT NULL CHECK (phases IN (1, 3)),
  phase_mode TEXT NOT NULL CHECK (phase_mode IN ('AUTO', 'FIXED', 'NONE')),
  phase_fixed TEXT NULL CHECK (phase_fixed IN ('A', 'B', 'C')),
  FOREIGN KEY(panel_id) REFERENCES panels(id) ON DELETE CASCADE,
  CHECK (phase_mode <> 'FIXED' OR phase_fixed IS NOT NULL),
  CHECK (phase_mode = 'FIXED' OR phase_fixed IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_rtm_rows_panel_id ON rtm_rows(panel_id);

-- Таблица коэффициентов Kr (PK(ne, ki))
CREATE TABLE IF NOT EXISTS kr_table (
  ne INTEGER NOT NULL,
  ki REAL NOT NULL,
  kr REAL NOT NULL,
  source TEXT NOT NULL,
  PRIMARY KEY (ne, ki)
);

CREATE INDEX IF NOT EXISTS idx_kr_table_ne ON kr_table(ne);
CREATE INDEX IF NOT EXISTS idx_kr_table_ki ON kr_table(ki);

-- Расчёт по строке РТМ (на одну строку ввода)
CREATE TABLE IF NOT EXISTS rtm_row_calc (
  row_id TEXT PRIMARY KEY,
  pn_total REAL,
  ki_pn REAL,
  ki_pn_tg REAL,
  n_pn2 REAL,
  FOREIGN KEY(row_id) REFERENCES rtm_rows(id) ON DELETE CASCADE
);

-- Итоги по щиту (РТМ)
CREATE TABLE IF NOT EXISTS rtm_panel_calc (
  panel_id TEXT PRIMARY KEY,
  sum_pn REAL,
  sum_ki_pn REAL,
  sum_ki_pn_tg REAL,
  sum_np2 REAL,
  ne REAL,
  kr REAL,
  pp_kw REAL,
  qp_kvar REAL,
  sp_kva REAL,
  ip_a REAL,
  updated_at TEXT,
  FOREIGN KEY(panel_id) REFERENCES panels(id) ON DELETE CASCADE
);

-- Итоги фазировки по щиту
CREATE TABLE IF NOT EXISTS panel_phase_calc (
  panel_id TEXT PRIMARY KEY,
  ia_a REAL,
  ib_a REAL,
  ic_a REAL,
  imax_a REAL,
  iavg_a REAL,
  unbalance_pct REAL,
  method TEXT,
  updated_at TEXT,
  FOREIGN KEY(panel_id) REFERENCES panels(id) ON DELETE CASCADE
);

