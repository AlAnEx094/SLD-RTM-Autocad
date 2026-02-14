-- seed_kr_table.sql
-- Минимальный seed для MVP-0.1.
-- ВНИМАНИЕ: данные частичные и предназначены только для тестов/демо.
-- Обязательное покрытие:
-- - строка ne=4
-- - столбцы ki=0.6/0.7/0.8 (из примеров проекта)

PRAGMA foreign_keys = ON;

INSERT OR REPLACE INTO kr_table (ne, ki, kr, source) VALUES
  (4, 0.60, 1.12, 'RTM_36.18.32.4-92_Table_1_EXAMPLE'),
  (4, 0.70, 1.06, 'RTM_36.18.32.4-92_Table_1_EXAMPLE'),
  (4, 0.80, 1.00, 'RTM_36.18.32.4-92_Table_1_EXAMPLE');

-- TODO(MVP>0.1): заполнить остальные строки ne и столбцы ki по РТМ (Таблица 1).

