-- checks_kr_table.sql
-- Проверки полноты таблицы kr_table по РТМ 36.18.32.4-92, табл. 1 (<= 1000 В).

PRAGMA foreign_keys = ON;

SELECT CASE
  WHEN (SELECT COUNT(*) FROM kr_table) = 315 THEN 1
  ELSE (SELECT 1 FROM __kr_table_check_total_rows__)
END AS check_total_rows;

SELECT CASE
  WHEN (SELECT COUNT(DISTINCT ki) FROM kr_table) = 9 THEN 1
  ELSE (SELECT 1 FROM __kr_table_check_distinct_ki__)
END AS check_distinct_ki;

SELECT CASE
  WHEN (SELECT COUNT(DISTINCT ne) FROM kr_table) = 35 THEN 1
  ELSE (SELECT 1 FROM __kr_table_check_distinct_ne__)
END AS check_distinct_ne;

SELECT CASE
  WHEN (
    SELECT COUNT(DISTINCT source) = 1
      AND MIN(source) = 'RTM36.18.32.4-92_tab1'
      AND MAX(source) = 'RTM36.18.32.4-92_tab1'
    FROM kr_table
  ) THEN 1
  ELSE (SELECT 1 FROM __kr_table_check_source__)
END AS check_single_source;
