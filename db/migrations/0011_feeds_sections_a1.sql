-- 0011_feeds_sections_a1.sql
-- A1: decouple bus section numbering from feed roles; add explicit panel feeds and section-feed links.
-- Backward compatible, additive migration.

PRAGMA foreign_keys = ON;

-- 1) bus_sections: numeric identity + optional display label.
ALTER TABLE bus_sections ADD COLUMN section_no INTEGER;
ALTER TABLE bus_sections ADD COLUMN section_label TEXT;

-- Ensure every existing panel has at least one section.
INSERT INTO bus_sections (id, panel_id, name, section_no, section_label)
SELECT lower(hex(randomblob(16))), p.id, 'DEFAULT', 1, NULL
FROM panels p
WHERE NOT EXISTS (
  SELECT 1 FROM bus_sections bs WHERE bs.panel_id = p.id
);

-- Explicit rule: legacy DEFAULT section gets number 1 when missing.
UPDATE bus_sections
SET section_no = 1
WHERE section_no IS NULL AND UPPER(COALESCE(name, '')) = 'DEFAULT';

-- Backfill remaining section numbers with stable per-panel ordering.
WITH panel_offsets AS (
  SELECT panel_id, COALESCE(MAX(section_no), 0) AS base
  FROM bus_sections
  GROUP BY panel_id
),
ordered AS (
  SELECT
    bs.id,
    bs.panel_id,
    ROW_NUMBER() OVER (
      PARTITION BY bs.panel_id
      ORDER BY LOWER(COALESCE(bs.name, '')), bs.id
    ) AS rn
  FROM bus_sections bs
  WHERE bs.section_no IS NULL
)
UPDATE bus_sections
SET section_no = (
  SELECT po.base + o.rn
  FROM ordered o
  JOIN panel_offsets po ON po.panel_id = o.panel_id
  WHERE o.id = bus_sections.id
)
WHERE section_no IS NULL;

CREATE INDEX IF NOT EXISTS idx_bus_sections_panel_section_no ON bus_sections(panel_id, section_no);

-- Auto-create DEFAULT section for new panels.
CREATE TRIGGER IF NOT EXISTS trg_panels_default_bus_section
AFTER INSERT ON panels
WHEN NOT EXISTS (SELECT 1 FROM bus_sections bs WHERE bs.panel_id = NEW.id)
BEGIN
  INSERT INTO bus_sections (id, panel_id, name, section_no, section_label)
  VALUES (lower(hex(randomblob(16))), NEW.id, 'DEFAULT', 1, NULL);
END;

-- 2) feed roles: ensure A1 roles are present (keep legacy DC for compatibility).
INSERT INTO feed_roles (id, code, title_ru, title_en, is_default) VALUES
  ('MAIN', 'MAIN', 'Основной', 'Main', 1),
  ('RESERVE', 'RESERVE', 'Резервный', 'Reserve', 0),
  ('DG', 'DG', 'ДГУ', 'DG', 0),
  ('UPS', 'UPS', 'ИБП', 'UPS', 0),
  ('OTHER', 'OTHER', 'Прочий', 'Other', 0),
  ('DC', 'DC', 'DC', 'DC', 0)
ON CONFLICT(code) DO UPDATE SET
  title_ru = excluded.title_ru,
  title_en = excluded.title_en,
  is_default = excluded.is_default;

-- 3) consumer_feeds: keep legacy priority and add explicit feed_priority.
ALTER TABLE consumer_feeds ADD COLUMN feed_priority INTEGER NOT NULL DEFAULT 1;
UPDATE consumer_feeds
SET feed_priority = COALESCE(priority, feed_priority, 1);

-- 4) explicit feeds entity (panel-level).
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

-- 5) explicit relation: bus section supplied by one or more feeds.
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

-- 6) Data migration: synthesize panel feeds from existing consumer_feeds (deduplicated).
WITH feed_candidates AS (
  SELECT DISTINCT
    c.panel_id AS panel_id,
    CASE
      WHEN cf.feed_role_id IS NOT NULL THEN cf.feed_role_id
      WHEN cf.feed_role = 'NORMAL' THEN 'MAIN'
      WHEN cf.feed_role = 'RESERVE' THEN 'RESERVE'
      ELSE 'OTHER'
    END AS role,
    COALESCE(cf.feed_priority, cf.priority, 1) AS priority
  FROM consumer_feeds cf
  JOIN consumers c ON c.id = cf.consumer_id
)
INSERT INTO feeds (id, panel_id, name, role, priority, source_panel_id)
SELECT
  lower(hex(randomblob(16))),
  fc.panel_id,
  fc.role || ' #' || CAST(fc.priority AS TEXT),
  fc.role,
  fc.priority,
  NULL
FROM feed_candidates fc
WHERE fc.role IN (SELECT id FROM feed_roles)
  AND NOT EXISTS (
    SELECT 1
    FROM feeds f
    WHERE f.panel_id = fc.panel_id
      AND f.role = fc.role
      AND f.priority = fc.priority
  );

-- 7) Data migration: map section supply from consumer feeds to bus_section_feeds.
WITH section_feed_candidates AS (
  SELECT DISTINCT
    cf.bus_section_id AS bus_section_id,
    c.panel_id AS panel_id,
    CASE
      WHEN cf.feed_role_id IS NOT NULL THEN cf.feed_role_id
      WHEN cf.feed_role = 'NORMAL' THEN 'MAIN'
      WHEN cf.feed_role = 'RESERVE' THEN 'RESERVE'
      ELSE 'OTHER'
    END AS role,
    COALESCE(cf.feed_priority, cf.priority, 1) AS priority
  FROM consumer_feeds cf
  JOIN consumers c ON c.id = cf.consumer_id
)
INSERT OR IGNORE INTO bus_section_feeds (id, bus_section_id, feed_id, mode, is_active_default)
SELECT
  lower(hex(randomblob(16))),
  sfc.bus_section_id,
  f.id,
  CASE
    WHEN sfc.role = 'MAIN' THEN 'NORMAL'
    ELSE 'EMERGENCY'
  END AS mode,
  1
FROM section_feed_candidates sfc
JOIN feeds f
  ON f.panel_id = sfc.panel_id
 AND f.role = sfc.role
 AND f.priority = sfc.priority;
