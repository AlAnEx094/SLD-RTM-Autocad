-- seed_cable_sections.sql
-- Стандартный ряд сечений кабеля (мм2)

-- Idempotent seed (safe to run multiple times)
INSERT OR IGNORE INTO cable_sections (s_mm2) VALUES
  (1.5),
  (2.5),
  (4),
  (6),
  (10),
  (16),
  (25),
  (35),
  (50),
  (70),
  (95),
  (120),
  (150),
  (185),
  (240);
