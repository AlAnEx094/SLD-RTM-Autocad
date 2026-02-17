# DB_ENGINEER TASK — Phase Balance v0.1.1 (phase_source)

ROLE: DB_ENGINEER  
BRANCH: `feature/phase-source-db` (создавай изменения и коммиты только здесь)  
SCOPE (разрешено менять): **только `db/*` SQL файлы** (`db/migrations/*.sql`, `db/schema.sql`)  
SCOPE (запрещено менять): `calc_core/*`, `tools/*`, `app/*`, `tests/*`, `docs/*`, `dwg/*`

## Источник требований

- `docs/contracts/PHASE_BALANCE_V0_1.md` — базовый контракт балансировки
- Sprint v0.1.1: защитить MANUAL назначения (phase_source)

## Цель (обязательно)

Добавить поддержку источника назначения фазы (`AUTO`/`MANUAL`) для защиты ручных назначений:

### 1) `circuits.phase_source` (обязательно)

Добавить столбец в `circuits`:

- `circuits.phase_source TEXT NOT NULL DEFAULT 'AUTO' CHECK (phase_source IN ('AUTO','MANUAL'))`

Примечания:

- В SQLite `ALTER TABLE ... ADD COLUMN` **не идемпотентен**; миграция рассчитывает на `schema_migrations` (каждый номер применяем один раз).

### 2) `db/schema.sql` snapshot (обязательно)

Обновить агрегированный слепок схемы:

- отразить `circuits.phase_source`
- явно не трогать `panel_phase_calc` (legacy RTM A/B/C)

## Acceptance criteria

- Прогон миграций на пустой БД проходит без ошибок.
- `circuits.phase_source` имеет CHECK на `AUTO|MANUAL` и default `AUTO`.
- `db/schema.sql` соответствует миграциям.

## Git workflow (обязательно)

1) `git checkout -b feature/phase-source-db` (или `git checkout feature/phase-source-db`)
2) Правки только в `db/*`
3) `git add db`
4) `git commit -m "db: add circuits.phase_source"`
