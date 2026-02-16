# DB_ENGINEER TASK — Phase Balance v0.1 (DB = truth)

ROLE: DB_ENGINEER  
BRANCH: `feature/phase-balance-db` (создавай изменения и коммиты только здесь)  
SCOPE (разрешено менять): **только `db/*` SQL файлы** (`db/migrations/*.sql`, `db/schema.sql`)  
SCOPE (запрещено менять): `calc_core/*`, `tools/*`, `app/*`, `tests/*`, `docs/*`, `dwg/*`

## Источник требований

- `docs/contracts/PHASE_BALANCE_V0_1.md` — контракт вход/выход/формулы/ограничения

## Цель (обязательно)

Добавить персистентную поддержку фазной балансировки 1Ф цепей:

### 1) `circuits.phase` (обязательно)

Добавить столбец:

- `circuits.phase TEXT NULL CHECK (phase IN ('L1','L2','L3'))`

Примечания:

- NULL разрешён (для 3Ф цепей или до выполнения балансировки).
- В SQLite `ALTER TABLE ... ADD COLUMN` **не идемпотентен**; миграция рассчитывает на `schema_migrations` (каждый номер применяем один раз).

### 2) Таблица агрегата `panel_phase_balance` (обязательно)

Создать таблицу:

`panel_phase_balance(panel_id, mode, i_l1, i_l2, i_l3, unbalance_pct, updated_at)`

Требования:

- `panel_id` FK → `panels(id)` `ON DELETE CASCADE`
- `mode` ∈ {`NORMAL`, `EMERGENCY`} (CHECK)
- `PRIMARY KEY(panel_id, mode)`
- индексы по `panel_id` и `mode` (или обосновать, почему не нужны)

### 3) `db/schema.sql` snapshot (обязательно)

Обновить агрегированный слепок схемы:

- отразить `circuits.phase`
- добавить `panel_phase_balance` + индексы
- явно не трогать `panel_phase_calc` (legacy RTM A/B/C)

## Acceptance criteria

- Прогон миграций на пустой БД проходит без ошибок.
- `circuits.phase` имеет CHECK на `L1/L2/L3`.
- `panel_phase_balance` существует и имеет PK `(panel_id, mode)`.
- `db/schema.sql` соответствует миграциям.

## Git workflow (обязательно)

1) `git checkout -b feature/phase-balance-db` (или `git checkout feature/phase-balance-db`)
2) Правки только в `db/*`
3) `git add db`
4) `git commit -m "db: add phase balance storage"`
