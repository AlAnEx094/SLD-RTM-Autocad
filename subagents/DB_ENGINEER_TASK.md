# DB_ENGINEER TASK — feature/db-layer (MVP-0.3 Bus sections + consumers feeds)

ROLE: DB_ENGINEER  
BRANCH: `feature/db-layer` (создать изменения и коммиты только здесь)  
SCOPE (разрешено менять): **только `db/*` SQL файлы**  
SCOPE (запрещено менять): `calc_core/*`, `tools/*`, `tests/*`, `docs/*`, `cad_adapter/*`

## Контекст

MVP-0.3 добавляет поддержку потребителя 1 категории с двумя вводами:
`NORMAL`/`RESERVE` от разных секций шин ЩСН.

Нужно хранить:
- секции шин (`bus_sections`)
- потребителей (`consumers`)
- привязки вводов потребителей к секциям (`consumer_feeds`)

Важно:
- DB = истина (ввод отдельно от расчёта).
- Никаких изменений в существующих `circuits/*` и ΔU-таблицах: они живут отдельно.

## Цель

### 1) Миграция `db/migrations/0003_bus_and_feeds.sql` (обязательно)

Добавить таблицы:

#### A) `bus_sections`

`bus_sections(id TEXT PK, panel_id TEXT FK, name TEXT NOT NULL)`

- `panel_id` -> `panels(id)` ON DELETE CASCADE

#### B) `consumers`

```sql
consumers(
  id TEXT PRIMARY KEY,
  panel_id TEXT NOT NULL REFERENCES panels(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  load_ref_type TEXT NOT NULL DEFAULT 'RTM_PANEL'
    CHECK(load_ref_type IN ('RTM_PANEL','RTM_ROW','MANUAL')),
  load_ref_id TEXT NOT NULL,
  notes TEXT
)
```

MVP-решение для тестов: поддержать `MANUAL` нагрузку прямо в `consumers` (чтобы не мокать RTM):

- добавить nullable-поля:
  - `p_kw REAL`
  - `q_kvar REAL`
  - `s_kva REAL`
  - `i_a REAL`
- добавить CHECK:
  - если `load_ref_type='MANUAL'` → все 4 поля NOT NULL
  - если `load_ref_type<>'MANUAL'` → все 4 поля NULL

#### C) `consumer_feeds`

```sql
consumer_feeds(
  id TEXT PRIMARY KEY,
  consumer_id TEXT NOT NULL REFERENCES consumers(id) ON DELETE CASCADE,
  bus_section_id TEXT NOT NULL REFERENCES bus_sections(id) ON DELETE CASCADE,
  feed_role TEXT NOT NULL CHECK(feed_role IN ('NORMAL','RESERVE'))
)
```

Опциональные индексы:
- `consumer_feeds(consumer_id)`
- `consumer_feeds(bus_section_id)`

### 2) Миграция данных: default bus section (обязательно)

Требование: для каждого `panels.id` должна существовать хотя бы 1 запись `bus_sections`
с именем `'DEFAULT'`, если для панели секций ещё нет.

Сделать это в конце `0003_bus_and_feeds.sql` через `INSERT ... SELECT`:
- вставить `'DEFAULT'` для каждой панели, где `NOT EXISTS (bus_sections WHERE panel_id = panels.id)`
- `id` генерировать внутри SQLite (например `lower(hex(randomblob(16)))`), т.к. Python/CLI не должны быть обязательны для миграции.

### 3) Обновить `db/schema.sql` (обязательно)

Добавить в snapshot новые таблицы и (если добавлялись) MANUAL поля в `consumers`.

## Deliverables

- `db/migrations/0003_bus_and_feeds.sql`
- Обновлённый `db/schema.sql`

## Acceptance criteria

- На пустой БД последовательное выполнение:
  - `db/migrations/0001_init.sql`
  - `db/migrations/0002_circuits.sql`
  - `db/migrations/0003_bus_and_feeds.sql`
  - `db/seed_cable_sections.sql`
  проходит без ошибок.
- Таблицы `bus_sections`, `consumers`, `consumer_feeds` созданы и имеют нужные ограничения.
- При наличии панелей (например, если миграция накатывается на непустую БД) после `0003`:
  - для каждой панели есть хотя бы одна `bus_sections` (DEFAULT), если ранее не было секций.
- CHECK-ограничение для MANUAL нагрузки работает (MANUAL требует p/q/s/i, non-MANUAL запрещает их).

## Git workflow (обязательно)

1) `git checkout -b feature/db-layer` (или `git checkout feature/db-layer`, если уже существует)
2) Правки только в `db/*`
3) `git add db`
4) `git commit -m "db: add bus sections and consumer feeds (MVP-0.3)"`


