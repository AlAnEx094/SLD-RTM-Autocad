-- 0005_feeds_v2_refs.sql
-- Feeds v2: feed_roles, modes, consumer_feeds v2 columns, consumer_mode_rules.
-- Backward-tolerant: maps v1 feed_role NORMAL->MAIN, RESERVE->RESERVE.

PRAGMA foreign_keys = ON;

-- 1) feed_roles reference table
CREATE TABLE IF NOT EXISTS feed_roles (
  id TEXT PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,
  title_ru TEXT,
  title_en TEXT,
  is_default INT NOT NULL DEFAULT 0
);

INSERT INTO feed_roles (id, code, title_ru, title_en, is_default) VALUES
  ('MAIN', 'MAIN', 'Основной', 'Main', 1),
  ('RESERVE', 'RESERVE', 'Резервный', 'Reserve', 0),
  ('DG', 'DG', 'ДГУ', 'DG', 0),
  ('DC', 'DC', 'DC', 'DC', 0),
  ('UPS', 'UPS', 'ИБП', 'UPS', 0)
ON CONFLICT(code) DO UPDATE SET
  title_ru = excluded.title_ru,
  title_en = excluded.title_en,
  is_default = excluded.is_default;

-- 2) modes reference table
CREATE TABLE IF NOT EXISTS modes (
  id TEXT PRIMARY KEY,
  code TEXT UNIQUE NOT NULL
);

INSERT OR IGNORE INTO modes (id, code) VALUES
  ('NORMAL', 'NORMAL'),
  ('EMERGENCY', 'EMERGENCY');

-- 3) consumer_feeds: add feed_role_id and priority
ALTER TABLE consumer_feeds ADD COLUMN feed_role_id TEXT REFERENCES feed_roles(id);
ALTER TABLE consumer_feeds ADD COLUMN priority INT NOT NULL DEFAULT 1;

-- Backward-tolerant data migration: v1 feed_role -> feed_role_id (idempotent)
UPDATE consumer_feeds
SET feed_role_id = CASE
  WHEN feed_role = 'NORMAL' THEN 'MAIN'
  WHEN feed_role = 'RESERVE' THEN 'RESERVE'
  ELSE feed_role_id
END
WHERE feed_role_id IS NULL AND feed_role IN ('NORMAL', 'RESERVE');

-- 4) consumer_mode_rules table
CREATE TABLE IF NOT EXISTS consumer_mode_rules (
  consumer_id TEXT NOT NULL REFERENCES consumers(id) ON DELETE CASCADE,
  mode_id TEXT NOT NULL REFERENCES modes(id),
  active_feed_role_id TEXT NOT NULL REFERENCES feed_roles(id),
  PRIMARY KEY (consumer_id, mode_id)
);

CREATE INDEX IF NOT EXISTS idx_consumer_mode_rules_consumer_id ON consumer_mode_rules(consumer_id);
CREATE INDEX IF NOT EXISTS idx_consumer_mode_rules_mode_id ON consumer_mode_rules(mode_id);

-- Best-effort default rules for existing consumers (idempotent)
INSERT OR IGNORE INTO consumer_mode_rules (consumer_id, mode_id, active_feed_role_id)
SELECT c.id, 'NORMAL', 'MAIN' FROM consumers c;

INSERT OR IGNORE INTO consumer_mode_rules (consumer_id, mode_id, active_feed_role_id)
SELECT c.id, 'EMERGENCY', 'RESERVE' FROM consumers c;
