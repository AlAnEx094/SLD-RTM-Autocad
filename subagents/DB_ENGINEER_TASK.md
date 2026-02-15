# DB_ENGINEER TASK — feature/db-layer (MVP-0.2 Voltage Drop / Circuits)

ROLE: DB_ENGINEER  
BRANCH: `feature/db-layer` (создать изменения и коммиты только здесь)  
SCOPE (разрешено менять): **только `db/*` SQL файлы**  
SCOPE (запрещено менять): `calc_core/*`, `tools/*`, `tests/*`, `docs/*`, `cad_adapter/*`

## Контекст

MVP-0.2 добавляет расчёт падения напряжения ΔU и подбор минимального сечения по ΔU.
Для этого нужен DB-слой: сущность **circuits** + результаты **circuit_calc**, а также
кастомные лимиты ΔU на панели.

Важно:
- DB = истина (ввод отдельно от расчёта).
- Никаких изменений в существующих сущностях Kr (`kr_table`) и расчётных таблицах RTM.

## Цель

### 1) Миграция `db/migrations/0002_circuits.sql` (обязательно)

Добавить:

#### A) Поля лимитов ΔU в `panels`

- `panels.du_limit_lighting_pct REAL NOT NULL DEFAULT 3.0`
- `panels.du_limit_other_pct REAL NOT NULL DEFAULT 5.0`
- (опционально) `panels.installation_type TEXT DEFAULT 'A'`

Примечание: `installation_type` не должен влиять на расчёт в MVP-0.2, лимиты решают всё.

#### B) Таблицы `circuits`, `circuit_calc`, `cable_sections`

Создать таблицы (SQLite):

- `circuits`:
  - `id TEXT PRIMARY KEY`
  - `panel_id TEXT NOT NULL REFERENCES panels(id) ON DELETE CASCADE`
  - `name TEXT`
  - `phases INTEGER NOT NULL CHECK(phases IN (1,3))`
  - `neutral_present INTEGER NOT NULL DEFAULT 1`
  - `unbalance_mode TEXT NOT NULL DEFAULT 'NORMAL' CHECK(unbalance_mode IN ('NORMAL','FULL_UNBALANCED'))`
  - `length_m REAL NOT NULL`  (метры)
  - `material TEXT NOT NULL CHECK(material IN ('CU','AL'))`
  - `cos_phi REAL NOT NULL`
  - `load_kind TEXT NOT NULL DEFAULT 'OTHER' CHECK(load_kind IN ('LIGHTING','OTHER'))`
  - `i_calc_a REAL NOT NULL`  (РЕШЕНИЕ MVP: задаётся пользователем/внешним расчётом, CalcCore только использует)

- `circuit_calc`:
  - `circuit_id TEXT PRIMARY KEY REFERENCES circuits(id) ON DELETE CASCADE`
  - `i_calc_a REAL NOT NULL`
  - `du_v REAL NOT NULL`
  - `du_pct REAL NOT NULL`
  - `du_limit_pct REAL NOT NULL`
  - `s_mm2_selected REAL NOT NULL`
  - `method TEXT NOT NULL`
  - `updated_at TEXT NOT NULL`

- `cable_sections`:
  - `s_mm2 REAL PRIMARY KEY`

Индексы (минимально необходимые):
- `circuits(panel_id)`

### 2) Seed сечений кабеля (обязательно)

Добавить файл `db/seed_cable_sections.sql`:

- Заполняет `cable_sections` стандартным рядом сечений (мм²) в диапазоне **1.5..240**:
  `1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240`

Формат:

```sql
INSERT OR IGNORE INTO cable_sections (s_mm2) VALUES
  (1.5),
  (2.5),
  ...
;
```

### 3) Обновить `db/schema.sql` (обязательно)

`db/schema.sql` — агрегированный “слепок” схемы. Обнови его так, чтобы он отражал изменения
после применения `0002_circuits.sql` (новые таблицы + новые колонки в `panels`).

## Deliverables

- `db/migrations/0002_circuits.sql`
- `db/seed_cable_sections.sql`
- Обновлённый `db/schema.sql`

## Acceptance criteria

- На пустой БД последовательное выполнение:
  - `db/migrations/0001_init.sql`
  - `db/migrations/0002_circuits.sql`
  - `db/seed_cable_sections.sql`
  проходит без ошибок.
- В `panels` есть колонки `du_limit_lighting_pct`, `du_limit_other_pct` с дефолтами 3.0/5.0.
- Таблицы `circuits`, `circuit_calc`, `cable_sections` созданы и имеют нужные ограничения.

## Git workflow (обязательно)

1) `git checkout -b feature/db-layer` (или `git checkout feature/db-layer`, если уже существует)
2) Правки только в `db/*`
3) `git add db`
4) `git commit -m "db: add circuits and voltage-drop limits (MVP-0.2)"`


