-- 0003_bus_and_feeds.sql
-- MVP-0.3: Секции шин + потребители + питания (NORMAL/RESERVE)
-- для поддержки потребителей 1-й категории с двумя вводами.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS bus_sections (
  id TEXT PRIMARY KEY,
  panel_id TEXT NOT NULL REFERENCES panels(id) ON DELETE CASCADE,
  name TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bus_sections_panel_id ON bus_sections(panel_id);

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

CREATE TABLE IF NOT EXISTS consumer_feeds (
  id TEXT PRIMARY KEY,
  consumer_id TEXT NOT NULL REFERENCES consumers(id) ON DELETE CASCADE,
  bus_section_id TEXT NOT NULL REFERENCES bus_sections(id) ON DELETE CASCADE,
  feed_role TEXT NOT NULL CHECK (feed_role IN ('NORMAL', 'RESERVE'))
);

CREATE INDEX IF NOT EXISTS idx_consumer_feeds_consumer_id ON consumer_feeds(consumer_id);
CREATE INDEX IF NOT EXISTS idx_consumer_feeds_bus_section_id ON consumer_feeds(bus_section_id);

-- Data migration:
-- Для каждого существующего щита — гарантировать хотя бы одну секцию шин.
-- Если у щита ещё нет ни одной секции, создать 'DEFAULT'.
INSERT INTO bus_sections (id, panel_id, name)
SELECT lower(hex(randomblob(16))), p.id, 'DEFAULT'
FROM panels p
WHERE NOT EXISTS (
  SELECT 1 FROM bus_sections bs WHERE bs.panel_id = p.id
);

