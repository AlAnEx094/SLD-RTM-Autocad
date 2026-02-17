# DB_ENGINEER TASK — MVP-BAL v0.1.2 (phase balance warnings)

ROLE: DB_ENGINEER  
BRANCH: `feature/pb-warn-db` (создавай изменения и коммиты только здесь)  
SCOPE (разрешено менять): **только `db/*` SQL файлы** (`db/migrations/*.sql`, `db/schema.sql`)  
SCOPE (запрещено менять): `calc_core/*`, `tools/*`, `app/*`, `tests/*`, `docs/*`, `dwg/*`

## Источник требований

- `docs/contracts/PHASE_BALANCE_V0_1.md` — базовый контракт балансировки
- Sprint v0.1.2: предупреждения для MANUAL цепей с невалидной фазой (DB-backed)

## Цель (обязательно)

Устранить “тихие ошибки”: сохранять предупреждения в БД, если `phase_source='MANUAL'`, но `phase` пустой/невалидный.

### 1) `panel_phase_balance` warning columns (обязательно)

Миграция должна добавить в `panel_phase_balance`:

- `invalid_manual_count INT NOT NULL DEFAULT 0`
- `warnings_json TEXT NULL`

Примечания:

- В SQLite `ALTER TABLE ... ADD COLUMN` **не идемпотентен**; миграция рассчитывает на `schema_migrations` (каждый номер применяем один раз).

### 2) `db/schema.sql` snapshot (обязательно)

Обновить агрегированный слепок схемы:

- отразить новые поля `panel_phase_balance.invalid_manual_count` и `panel_phase_balance.warnings_json`
- явно не трогать `panel_phase_calc` (legacy RTM A/B/C)

## Acceptance criteria

- Прогон миграций на пустой БД проходит без ошибок.
- `panel_phase_balance` имеет новые поля и default значения корректны.
- `db/schema.sql` соответствует миграциям.

## Git workflow (обязательно)

1) `git checkout -b feature/pb-warn-db` (или `git checkout feature/pb-warn-db`)
2) Правки только в `db/*`
3) `git add db`
4) `git commit -m "db: store phase balance warnings"`
