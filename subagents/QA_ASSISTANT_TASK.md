# QA_ASSISTANT TASK — Feeds v2 migration + section_calc v2 tests

ROLE: QA_ASSISTANT  
BRANCH: `feature/feeds-v2-qa` (создавай изменения и коммиты только здесь)  
SCOPE (разрешено менять): `tests/*`  
SCOPE (запрещено менять): `db/*`, `calc_core/*`, `tools/*`, `app/*`, `docs/*`, `dwg/*`

## Контекст

Sprint вводит:

- Feeds v2 schema (roles/modes/rules/priority)
- Feeds v2 calc (section_calc агрегируется по mode NORMAL/EMERGENCY)

Твоя задача — high-signal тесты на миграцию и корректность агрегации.

Источник требований:

- `docs/ui/FEEDS_V2_SPEC.md`
- `docs/contracts/SECTION_AGG_V2.md` (будет добавлен calc-инженером)

## Что нужно сделать (обязательно)

### 1) Тест миграции Feeds v2 (обязательно)

Добавить тест (например `tests/test_feeds_v2_migration.py`), который:

- создаёт tmp SQLite
- накатывает миграции последовательно (как в остальных тестах проекта)
- проверяет:
  - seeded `feed_roles` содержит коды: MAIN, RESERVE, DG, DC, UPS
  - seeded `modes` содержит коды: NORMAL, EMERGENCY

И отдельно проверить backward mapping:

- создать минимальную v1 структуру consumer_feeds с `feed_role='NORMAL'/'RESERVE'` (или создать через старые миграции и вставки),
- прогнать новую миграцию v2,
- убедиться, что:
  - `consumer_feeds.feed_role_id` заполнен
  - `NORMAL` замапплен в роль `MAIN`
  - `RESERVE` замапплен в роль `RESERVE`

### 2) Тест section_calc v2 (обязательно)

Добавить тест (например `tests/test_section_aggregation_v2.py`), который проверяет сценарий:

- consumer с двумя вводами:
  - MAIN → S1
  - RESERVE → S2
- mode=NORMAL ⇒ нагрузка только в S1
- mode=EMERGENCY ⇒ нагрузка только в S2

Требования к setup:

- загрузка consumer нагрузки:
  - можно использовать `MANUAL` (p/q/s/i) для изоляции теста
- mode rules:
  - либо вставить `consumer_mode_rules` явно
  - либо полагаться на default‑логику calc (если так реализовано) — но тогда тест должен явно это проверять

### 3) Обновить/починить существующие тесты, которые используют RESERVE (обязательно)

Проект сейчас имеет тесты, завязанные на `mode='RESERVE'` и `--sections-mode` choices.
После v2:

- `section_calc.mode` должен быть `NORMAL/EMERGENCY`
- CLI `--sections-mode` должен быть `NORMAL/EMERGENCY`

Требование: `pytest -q` зелёный.

## Acceptance criteria

- Добавлены тесты миграции и section_calc v2.
- Все тесты проходят (`pytest -q`).

## Git workflow (обязательно)

1) `git checkout -b feature/feeds-v2-qa` (или `git checkout feature/feeds-v2-qa`)
2) Правки только в `tests/*`
3) `git add tests`
4) `git commit -m "test: add feeds v2 migration and aggregation coverage"`

