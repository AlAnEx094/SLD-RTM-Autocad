-- 0011_feeds_sections_a1.sql
-- A1: split bus section numbering from feed roles, add explicit feeds and bus_section_feeds topology.

PRAGMA foreign_keys = ON;

-- 1) bus_sections: stable numeric section identity + optional label
ALTER TABLE bus_sections ADD COLUMN section_no INTEGER;
ALTER TABLE bus_sections ADD COLUMN section_label TEXT;

-- Deterministic numbering for existing rows where section_no is missing.
-- Ordering rule per panel: DEFAULT first, then name, then id.
WITH ordered AS (
  SELECT
    id,
    ROW_NUMBER() OVER (
      PARTITION BY panel_id
      ORDER BY CASE WHEN UPPER(name) = 'DEFAULT' THEN 0 ELSE 1 END, name, id
    ) AS rn
  FROM bus_sections
)
UPDATE bus_sections
SET section_no = (
  SELECT rn FROM ordered WHERE ordered.id = bus_sections.id
)
WHERE section_no IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_bus_sections_panel_section_no
  ON bus_sections(panel_id, section_no)
  WHERE section_no IS NOT NULL;

-- 2) feed roles reference: ensure A1 role set includes OTHER (keep legacy codes).
INSERT INTO feed_roles (id, code, title_ru, title_en, is_default) VALUES
  ('MAIN', 'MAIN', 'Основной', 'Main', 1),
  ('RESERVE', 'RESERVE', 'Резервный', 'Reserve', 0),
  ('DG', 'DG', 'ДГУ', 'DG', 0),
  ('UPS', 'UPS', 'ИБП', 'UPS', 0),
  ('OTHER', 'OTHER', 'Прочее', 'Other', 0)
ON CONFLICT(code) DO UPDATE SET
  title_ru = excluded.title_ru,
  title_en = excluded.title_en,
  is_default = CASE WHEN excluded.code = 'MAIN' THEN 1 ELSE feed_roles.is_default END;

-- 3) consumer_feeds: explicit feed_priority (do not repurpose mode/feed_role legacy columns)
ALTER TABLE consumer_feeds ADD COLUMN feed_priority INTEGER NOT NULL DEFAULT 1;

UPDATE consumer_feeds
SET feed_priority = COALESCE(priority, 1)
WHERE feed_priority IS NULL OR feed_priority = 1;

-- 4) explicit panel feeds entity (future DWG topology)
CREATE TABLE IF NOT EXISTS feeds (
  id TEXT PRIMARY KEY,
  panel_id TEXT NOT NULL REFERENCES panels(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  role TEXT NOT NULL REFERENCES feed_roles(id),
  priority INTEGER NOT NULL DEFAULT 1,
  source_panel_id TEXT NULL REFERENCES panels(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_feeds_panel_id ON feeds(panel_id);
CREATE INDEX IF NOT EXISTS idx_feeds_role ON feeds(role);

-- Backfill feeds from existing consumer_feeds: dedupe by (panel, role), use minimal priority.
INSERT INTO feeds (id, panel_id, name, role, priority, source_panel_id)
SELECT
  lower(hex(randomblob(16))) AS id,
  c.panel_id,
  COALESCE(cf.feed_role_id,
    CASE
      WHEN cf.feed_role = 'NORMAL' THEN 'MAIN'
      WHEN cf.feed_role = 'RESERVE' THEN 'RESERVE'
      ELSE 'OTHER'
    END
  ) || ' FEED' AS name,
  COALESCE(cf.feed_role_id,
    CASE
      WHEN cf.feed_role = 'NORMAL' THEN 'MAIN'
      WHEN cf.feed_role = 'RESERVE' THEN 'RESERVE'
      ELSE 'OTHER'
    END
  ) AS role,
  MIN(COALESCE(cf.feed_priority, cf.priority, 1)) AS priority,
  NULL AS source_panel_id
FROM consumer_feeds cf
JOIN consumers c ON c.id = cf.consumer_id
GROUP BY c.panel_id,
         COALESCE(cf.feed_role_id,
            CASE
              WHEN cf.feed_role = 'NORMAL' THEN 'MAIN'
              WHEN cf.feed_role = 'RESERVE' THEN 'RESERVE'
              ELSE 'OTHER'
            END
         );

-- 5) explicit relation: bus section supplied by feed (mode-dependent mapping)
CREATE TABLE IF NOT EXISTS bus_section_feeds (
  bus_section_id TEXT NOT NULL REFERENCES bus_sections(id) ON DELETE CASCADE,
  feed_id TEXT NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
  mode TEXT NOT NULL CHECK(mode IN ('NORMAL', 'EMERGENCY')),
  is_active_default INTEGER NOT NULL DEFAULT 1 CHECK(is_active_default IN (0,1)),
  PRIMARY KEY (bus_section_id, feed_id, mode)
);

CREATE INDEX IF NOT EXISTS idx_bus_section_feeds_feed_id ON bus_section_feeds(feed_id);
CREATE INDEX IF NOT EXISTS idx_bus_section_feeds_mode ON bus_section_feeds(mode);

-- Backfill section->feed mapping for NORMAL mode from active role rules/default.
INSERT OR IGNORE INTO bus_section_feeds (bus_section_id, feed_id, mode, is_active_default)
SELECT DISTINCT
  cf.bus_section_id,
  f.id,
  'NORMAL' AS mode,
  1 AS is_active_default
FROM consumer_feeds cf
JOIN consumers c ON c.id = cf.consumer_id
LEFT JOIN consumer_mode_rules cmr
  ON cmr.consumer_id = c.id AND cmr.mode_id = 'NORMAL'
JOIN feeds f
  ON f.panel_id = c.panel_id
 AND f.role = COALESCE(cmr.active_feed_role_id, 'MAIN')
WHERE COALESCE(cf.feed_role_id,
        CASE
          WHEN cf.feed_role = 'NORMAL' THEN 'MAIN'
          WHEN cf.feed_role = 'RESERVE' THEN 'RESERVE'
          ELSE 'OTHER'
        END
      ) = COALESCE(cmr.active_feed_role_id, 'MAIN');

-- Backfill section->feed mapping for EMERGENCY mode from active role rules/default.
INSERT OR IGNORE INTO bus_section_feeds (bus_section_id, feed_id, mode, is_active_default)
SELECT DISTINCT
  cf.bus_section_id,
  f.id,
  'EMERGENCY' AS mode,
  1 AS is_active_default
FROM consumer_feeds cf
JOIN consumers c ON c.id = cf.consumer_id
LEFT JOIN consumer_mode_rules cmr
  ON cmr.consumer_id = c.id AND cmr.mode_id = 'EMERGENCY'
JOIN feeds f
  ON f.panel_id = c.panel_id
 AND f.role = COALESCE(cmr.active_feed_role_id, 'RESERVE')
WHERE COALESCE(cf.feed_role_id,
        CASE
          WHEN cf.feed_role = 'NORMAL' THEN 'MAIN'
          WHEN cf.feed_role = 'RESERVE' THEN 'RESERVE'
          ELSE 'OTHER'
        END
      ) = COALESCE(cmr.active_feed_role_id, 'RESERVE');
