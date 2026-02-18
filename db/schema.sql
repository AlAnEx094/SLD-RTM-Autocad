-- schema.sql
-- Агрегированный слепок схемы (MVP-0.3 + Feeds v2).
-- Источник истины для эволюции схемы — миграции в db/migrations/.
--
-- Схема: 0001..0011 (A1 feeds/sections model)

PRAGMA foreign_keys = ON;

-- Щиты
CREATE TABLE IF NOT EXISTS panels (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  system_type TEXT NOT NULL CHECK (system_type IN ('3PH', '1PH')),
  u_ll_v REAL,
  u_ph_v REAL,
  du_limit_lighting_pct REAL NOT NULL DEFAULT 3.0,
  du_limit_other_pct REAL NOT NULL DEFAULT 5.0,
  installation_type TEXT DEFAULT 'A'
);

-- Секции шин (внутри щита)
CREATE TABLE IF NOT EXISTS bus_sections (
  id TEXT PRIMARY KEY,
  panel_id TEXT NOT NULL REFERENCES panels(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  section_no INTEGER,
  section_label TEXT
);

CREATE INDEX IF NOT EXISTS idx_bus_sections_panel_id ON bus_sections(panel_id);
CREATE INDEX IF NOT EXISTS idx_bus_sections_panel_section_no ON bus_sections(panel_id, section_no);

CREATE TRIGGER IF NOT EXISTS trg_panels_default_bus_section
AFTER INSERT ON panels
WHEN NOT EXISTS (SELECT 1 FROM bus_sections bs WHERE bs.panel_id = NEW.id)
BEGIN
  INSERT INTO bus_sections (id, panel_id, name, section_no, section_label)
  VALUES (lower(hex(randomblob(16))), NEW.id, 'DEFAULT', 1, NULL);
END;

-- Потребители (могут ссылаться на РТМ либо задаваться вручную)
CREATE TABLE IF NOT EXISTS consumers (
  id TEXT PRIMARY KEY,
  panel_id TEXT NOT NULL REFERENCES panels(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  load_ref_type TEXT NOT NULL DEFAULT 'RTM_PANEL' CHECK (load_ref_type IN ('RTM_PANEL', 'RTM_ROW', 'MANUAL')),
  load_ref_id TEXT NOT NULL,
  notes TEXT,
  p_kw REAL,
  q_kvar REAL,
  s_kva REAL,
  i_a REAL,
  CHECK (
    (load_ref_type='MANUAL' AND p_kw IS NOT NULL AND q_kvar IS NOT NULL AND s_kva IS NOT NULL AND i_a IS NOT NULL)
    OR
    (load_ref_type<>'MANUAL' AND p_kw IS NULL AND q_kvar IS NULL AND s_kva IS NULL AND i_a IS NULL)
  )
);

CREATE INDEX IF NOT EXISTS idx_consumers_panel_id ON consumers(panel_id);

-- Справочник ролей вводов (Feeds v2)
CREATE TABLE IF NOT EXISTS feed_roles (
  id TEXT PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,
  title_ru TEXT,
  title_en TEXT,
  is_default INT NOT NULL DEFAULT 0
);

-- Справочник режимов расчёта (Feeds v2)
CREATE TABLE IF NOT EXISTS modes (
  id TEXT PRIMARY KEY,
  code TEXT UNIQUE NOT NULL
);

-- Питания потребителей (v2: feed_role_id + priority; feed_role deprecated)
CREATE TABLE IF NOT EXISTS consumer_feeds (
  id TEXT PRIMARY KEY,
  consumer_id TEXT NOT NULL REFERENCES consumers(id) ON DELETE CASCADE,
  bus_section_id TEXT NOT NULL REFERENCES bus_sections(id) ON DELETE CASCADE,
  feed_role TEXT CHECK (feed_role IN ('NORMAL', 'RESERVE')),
  feed_role_id TEXT REFERENCES feed_roles(id),
  priority INT NOT NULL DEFAULT 1,
  feed_priority INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_consumer_feeds_consumer_id ON consumer_feeds(consumer_id);
CREATE INDEX IF NOT EXISTS idx_consumer_feeds_bus_section_id ON consumer_feeds(bus_section_id);

-- Panel feeds (A1)
CREATE TABLE IF NOT EXISTS feeds (
  id TEXT PRIMARY KEY,
  panel_id TEXT NOT NULL REFERENCES panels(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  role TEXT NOT NULL REFERENCES feed_roles(id),
  priority INTEGER NOT NULL DEFAULT 1,
  source_panel_id TEXT NULL REFERENCES panels(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_feeds_panel_id ON feeds(panel_id);
CREATE INDEX IF NOT EXISTS idx_feeds_panel_role_priority ON feeds(panel_id, role, priority);

-- Section supply map: which feeds supply each bus section (A1)
CREATE TABLE IF NOT EXISTS bus_section_feeds (
  id TEXT PRIMARY KEY,
  bus_section_id TEXT NOT NULL REFERENCES bus_sections(id) ON DELETE CASCADE,
  feed_id TEXT NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
  mode TEXT NOT NULL CHECK(mode IN ('NORMAL', 'EMERGENCY')),
  is_active_default INTEGER NOT NULL DEFAULT 1 CHECK(is_active_default IN (0, 1)),
  UNIQUE(bus_section_id, feed_id, mode)
);

CREATE INDEX IF NOT EXISTS idx_bus_section_feeds_bus_section_id ON bus_section_feeds(bus_section_id);
CREATE INDEX IF NOT EXISTS idx_bus_section_feeds_feed_id ON bus_section_feeds(feed_id);

-- Правила выбора активной роли по режиму (Feeds v2)
CREATE TABLE IF NOT EXISTS consumer_mode_rules (
  consumer_id TEXT NOT NULL REFERENCES consumers(id) ON DELETE CASCADE,
  mode_id TEXT NOT NULL REFERENCES modes(id),
  active_feed_role_id TEXT NOT NULL REFERENCES feed_roles(id),
  PRIMARY KEY (consumer_id, mode_id)
);

CREATE INDEX IF NOT EXISTS idx_consumer_mode_rules_consumer_id ON consumer_mode_rules(consumer_id);
CREATE INDEX IF NOT EXISTS idx_consumer_mode_rules_mode_id ON consumer_mode_rules(mode_id);

-- Расчёт по секциям шин (v2: NORMAL/EMERGENCY)
CREATE TABLE IF NOT EXISTS section_calc (
  panel_id TEXT NOT NULL REFERENCES panels(id) ON DELETE CASCADE,
  bus_section_id TEXT NOT NULL REFERENCES bus_sections(id) ON DELETE CASCADE,
  mode TEXT NOT NULL CHECK(mode IN ('NORMAL','EMERGENCY')),
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
  phase TEXT NULL CHECK (phase IN ('L1','L2','L3')),
  phase_source TEXT NOT NULL DEFAULT 'AUTO' CHECK (phase_source IN ('AUTO','MANUAL')),
  bus_section_id TEXT NULL REFERENCES bus_sections(id) ON DELETE SET NULL,
  FOREIGN KEY(panel_id) REFERENCES panels(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_circuits_panel_id ON circuits(panel_id);
CREATE INDEX IF NOT EXISTS idx_circuits_bus_section_id ON circuits(bus_section_id);

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

-- Итоги фазировки по щиту (legacy: RTM A/B/C)
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

-- Балансировка фаз по 1Ф цепям (MVP-BAL v0.1: L1/L2/L3; v0.1.2: invalid_manual_count, warnings_json)
CREATE TABLE IF NOT EXISTS panel_phase_balance (
  panel_id TEXT NOT NULL REFERENCES panels(id) ON DELETE CASCADE,
  mode TEXT NOT NULL CHECK(mode IN ('NORMAL','EMERGENCY')),
  i_l1 REAL NOT NULL,
  i_l2 REAL NOT NULL,
  i_l3 REAL NOT NULL,
  unbalance_pct REAL NOT NULL,
  updated_at TEXT NOT NULL,
  invalid_manual_count INT NOT NULL DEFAULT 0,
  warnings_json TEXT NULL,
  PRIMARY KEY(panel_id, mode)
);

CREATE INDEX IF NOT EXISTS idx_panel_phase_balance_panel_id ON panel_phase_balance(panel_id);
CREATE INDEX IF NOT EXISTS idx_panel_phase_balance_mode ON panel_phase_balance(mode);
