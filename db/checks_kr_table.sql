-- checks_kr_table.sql
-- Проверки полноты таблицы kr_table по РТМ 36.18.32.4-92, табл. 1 (<= 1000 В).

PRAGMA foreign_keys = ON;

-- Эти проверки должны:
-- - возвращать 1 при успехе
-- - падать с ошибкой при несоответствии (используем деление на 0)

SELECT 1 / (CASE WHEN (SELECT COUNT(*) FROM kr_table) = 315 THEN 1 ELSE 0 END) AS check_total_rows;

SELECT 1 / (CASE WHEN (SELECT COUNT(DISTINCT ne) FROM kr_table) = 35 THEN 1 ELSE 0 END) AS check_distinct_ne;

SELECT 1 / (CASE WHEN (SELECT COUNT(DISTINCT ki) FROM kr_table) = 9 THEN 1 ELSE 0 END) AS check_distinct_ki;

-- Exact Ki set check
SELECT 1 / (
  CASE WHEN
    (SELECT COUNT(DISTINCT ki) FROM kr_table) = 9
    AND NOT EXISTS (
      SELECT 1
      FROM (SELECT DISTINCT ki FROM kr_table)
      WHERE ki NOT IN (0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80)
    )
  THEN 1 ELSE 0 END
) AS check_ki_set;

-- Single source check
SELECT 1 / (
  CASE WHEN
    (SELECT COUNT(DISTINCT source) FROM kr_table) = 1
    AND (SELECT MIN(source) FROM kr_table) = 'RTM36.18.32.4-92_tab1'
    AND (SELECT MAX(source) FROM kr_table) = 'RTM36.18.32.4-92_tab1'
  THEN 1 ELSE 0 END
) AS check_single_source;
