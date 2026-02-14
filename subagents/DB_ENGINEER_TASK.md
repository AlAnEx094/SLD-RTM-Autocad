# DB_ENGINEER TASK — feature/db-layer

ROLE: DB_ENGINEER  
BRANCH: `feature/db-layer` (создать изменения и коммиты только здесь)  
SCOPE (разрешено менять): **только `db/*` SQL файлы**  
SCOPE (запрещено менять): `calc_core/*`, `tools/*`, `tests/*`, `docs/*`, `cad_adapter/*`

## Контекст

Нужно устранить нормативную “дыру” и разнобой `source` в `kr_table` seed.

Требование: **полностью** заполнить `kr_table` значениями из **Таблицы 1 РТМ 36.18.32.4-92** (для сетей до 1000 В)
и унифицировать `source`.

Источник данных: локальный PDF **`57ea1c8c988b2.pdf`** (в окружении/репозитории).
Если PDF недоступен по имени в корне проекта — это **блокер**: не выдумывать значения.

## Цель

### A) Нормализовать `source` (обязательно)

Все записи Таблицы 1 должны иметь:

`source = 'RTM36.18.32.4-92_tab1'`

Никаких `*_EXAMPLE`, никаких `TODO_FILL_FROM_RTM` в финальном seed.

### B) Полностью заполнить `kr_table` (обязательно)

- Извлечь **всю** Таблицу 1 РТМ (<=1000 В): все строки `ne` и все столбцы `Ki`, которые есть в методике.
- Внести в `db/seed_kr_table.sql` **единым блоком**:

```sql
INSERT OR REPLACE INTO kr_table (ne, ki, kr, source) VALUES
  (...),
  (...),
  ...
;
```

Требования к данным:
- `ne`: INTEGER (все табличные значения, включая непоследовательные типа 17..25, 30, 35, 40, ... если они есть)
- `ki`: REAL ровно как в таблице (обычно 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80 и т.п.)
- `kr`: REAL **строго из таблицы**, без “на глаз”
- `source`: всегда `'RTM36.18.32.4-92_tab1'`

### C) Проверка целостности seed (желательно)

В конец `db/seed_kr_table.sql` добавь комментарий:

`-- EXPECTED: unique_ne = <N>, unique_ki = <M>, total_rows = N*M`

Опционально (если успеешь): добавь `db/checks_kr_table.sql`, который после загрузки проверяет:
- `SELECT COUNT(*)` == `N*M`
- набор `Ki` совпадает ожидаемому
- `SELECT source, COUNT(*) ...` даёт **ровно одну** строку `RTM36.18.32.4-92_tab1`

## Deliverables

- Обновить **только** `db/seed_kr_table.sql`
- (опционально) добавить `db/checks_kr_table.sql`
- Не менять `db/migrations/0001_init.sql` и `db/schema.sql`, если это не требуется

## Acceptance criteria

- В ветке `feature/db-layer` после изменений:
  - миграция + seed применяются на пустую SQLite без ошибок
  - `kr_table` заполнена полностью (матрица `ne x ki`, без дыр)
  - `source` в `kr_table` **один**: `'RTM36.18.32.4-92_tab1'`

## Git workflow (обязательно)

Выполни:

1) `git checkout feature/db-layer`
2) Внести правки только в `db/*`
3) `git add db/seed_kr_table.sql` (и `db/checks_kr_table.sql`, если добавлялся)
4) `git commit -m "db: fully seed kr_table from RTM table 1 (<=1000V) and normalize source"`

## Проверка

Запусти DB-only sanity check (не pytest):
- создать временную SQLite
- применить `db/migrations/0001_init.sql` + `db/seed_kr_table.sql`
- выполнить:
  - `SELECT COUNT(*) FROM kr_table;`
  - `SELECT COUNT(DISTINCT ne), COUNT(DISTINCT ki) FROM kr_table;`
  - `SELECT source, COUNT(*) FROM kr_table GROUP BY source;`

Если PDF `57ea1c8c988b2.pdf` не найден — **остановись и верни блокирующую проблему** (без “TODO” в данных).

