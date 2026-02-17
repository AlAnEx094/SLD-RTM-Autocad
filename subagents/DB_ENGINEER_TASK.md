# DB_ENGINEER TASK — MVP-BAL v0.3a (bind circuits to bus sections)

ROLE: DB_ENGINEER  
BRANCH: `feature/circuits-section-db` (создавай изменения и коммиты только здесь)  
SCOPE (разрешено менять): **только `db/*` SQL файлы** (`db/migrations/*.sql`, `db/schema.sql`)  
SCOPE (запрещено менять): `calc_core/*`, `tools/*`, `app/*`, `tests/*`, `docs/*`, `dwg/*`

## Источник требований

- `docs/contracts/PHASE_BALANCE_V0_3A.md` — контракт v0.3a (привязка цепей к секциям шин)

## Цель (обязательно)

Добавить связь `circuits` → `bus_sections`, чтобы `pb-mode=EMERGENCY` мог фильтровать цепи по активным аварийным секциям.

### 1) `circuits.bus_section_id` (обязательно)

Миграция должна добавить в `circuits`:

- `bus_section_id TEXT NULL REFERENCES bus_sections(id) ON DELETE SET NULL`

Рекомендуется:

- индекс `circuits(bus_section_id)` для быстрых выборок “цепи секции”

Примечания:

- В SQLite `ALTER TABLE ... ADD COLUMN` **не идемпотентен**; миграция рассчитывает на `schema_migrations` (каждый номер применяем один раз).

### 2) `db/schema.sql` snapshot (обязательно)

Обновить агрегированный слепок схемы:

- отразить новый столбец `circuits.bus_section_id` и FK/индекс
- явно не трогать `panel_phase_calc` (legacy RTM A/B/C)

## Acceptance criteria

- Прогон миграций на пустой БД проходит без ошибок.
- `db/schema.sql` соответствует миграциям.

## Git workflow (обязательно)

1) `git checkout -b feature/circuits-section-db` (или `git checkout feature/circuits-section-db`)
2) Правки только в `db/*`
3) `git add db`
4) `git commit -m "db: add circuits.bus_section_id"`
