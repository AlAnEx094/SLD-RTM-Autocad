# DB_ENGINEER TASK — Feeds v2 schema + backward-tolerant migration

ROLE: DB_ENGINEER  
BRANCH: `feature/feeds-v2-db` (создавай изменения и коммиты только здесь)  
SCOPE (разрешено менять): **только `db/*` SQL файлы** (`db/migrations/*.sql`, `db/schema.sql`)  
SCOPE (запрещено менять): `calc_core/*`, `tools/*`, `app/*`, `tests/*`, `docs/*`, `dwg/*`

## Контекст

Требования Sprint:

- i18n делается отдельно (UI‑ветка), **в DB ветке только схема/миграции**.
- Feeds v2 исправляет семантику: **роль ввода ≠ режим расчёта**.

Источник требований:

- `docs/ui/FEEDS_V2_SPEC.md` — термины/сущности/правила

Текущее v1:

- `consumer_feeds.feed_role` ∈ {`NORMAL`,`RESERVE`}
- `section_calc.mode` ∈ {`NORMAL`,`RESERVE`}

После v2:

- роли вводов: `feed_roles` (`MAIN/RESERVE/DG/DC/UPS`)
- режимы расчёта: `modes` (`NORMAL/EMERGENCY`)
- `consumer_feeds` хранит роль ввода + priority
- `section_calc.mode` хранит **режим расчёта** (`NORMAL/EMERGENCY`)

## Цель (что сделать)

### 1) Добавить справочники (обязательно)

#### A) `feed_roles`

Создать таблицу:

`feed_roles(id TEXT PK, code TEXT UNIQUE, title_ru TEXT, title_en TEXT, is_default INT)`

Seed (idempotent):

- MAIN (is_default=1)
- RESERVE
- DG
- DC
- UPS

#### B) `modes`

Создать таблицу:

`modes(id TEXT PK, code TEXT UNIQUE)`

Seed (idempotent):

- NORMAL
- EMERGENCY

### 2) Обновить `consumer_feeds` под v2 (обязательно)

Требования:

- добавить `feed_role_id` (FK → `feed_roles.id`)
- добавить `priority INT NOT NULL DEFAULT 1`
- старое поле `feed_role` (v1) **не использовать** в новой логике

Backward-tolerant data migration (обязательно):

- если в существующих данных есть `consumer_feeds.feed_role` (v1):
  - `NORMAL` → `MAIN`
  - `RESERVE` → `RESERVE`
- миграция должна быть идемпотентной:
  - не ломаться при повторном прогоне
  - не перетирать `feed_role_id`, если он уже заполнен

### 3) Добавить правила активной роли по режиму (обязательно)

Создать таблицу:

`consumer_mode_rules(consumer_id, mode_id, active_feed_role_id, PRIMARY KEY(consumer_id, mode_id))`

FK:

- `consumer_id` → `consumers.id` ON DELETE CASCADE
- `mode_id` → `modes.id`
- `active_feed_role_id` → `feed_roles.id`

Data migration (best-effort, рекомендуется):

- для всех существующих `consumers` вставить:
  - NORMAL → MAIN
  - EMERGENCY → RESERVE
- вставка должна быть idempotent (`INSERT ... ON CONFLICT DO NOTHING` или эквивалент).

### 4) Подготовить `section_calc` к v2 (обязательно, schema enabler)

`calc_core` после v2 будет писать:

- `section_calc.mode` ∈ {`NORMAL`,`EMERGENCY`}

Сейчас CHECK ограничивает `('NORMAL','RESERVE')`. Нужно сделать миграцию схемы:

- заменить `RESERVE` на `EMERGENCY` в допустимых значениях
- при необходимости выполнить best‑effort перенос данных:
  - существующие строки `section_calc.mode='RESERVE'` → `'EMERGENCY'`

Важно: SQLite не умеет ALTER CHECK напрямую — ожидается “create new table → copy → drop → rename”.

### 5) Обновить `db/schema.sql` snapshot (обязательно)

- Отразить новые таблицы `feed_roles`, `modes`, `consumer_mode_rules`
- Отразить изменения `consumer_feeds` (feed_role_id, priority; старое поле может оставаться)
- Отразить изменения `section_calc.mode` (NORMAL/EMERGENCY)

## Миграции (как оформить)

- Не модифицировать старые миграции `0001..0004`.
- Добавить новую(ые) миграцию(и) с новым номером(ами), например:
  - `0005_feeds_v2_refs.sql` (справочники + consumer_feeds + rules)
  - `0006_section_calc_mode_emergency.sql` (пересборка section_calc)

Номер/разбиение — на твоё усмотрение, но миграции должны применяться последовательно и быть идемпотентными там, где это реально.

## Acceptance criteria

- На пустой БД последовательный прогон `db/migrations/0001..0004` + новых `0005..` проходит без ошибок.
- `feed_roles` и `modes` seeded idempotent.
- В существующей БД с v1 данными:
  - `consumer_feeds.feed_role='NORMAL'` корректно маппится в `feed_role_id` роли `MAIN`
  - `consumer_feeds.feed_role='RESERVE'` корректно маппится в `feed_role_id` роли `RESERVE`
- Таблица `consumer_mode_rules` существует и принимает default‑правила.
- `section_calc` после миграции принимает `mode='EMERGENCY'`.

## Git workflow (обязательно)

1) `git checkout -b feature/feeds-v2-db` (или `git checkout feature/feeds-v2-db`)
2) Правки только в `db/*`
3) `git add db`
4) `git commit -m "db: add feeds v2 roles, modes, and migrations"`
