# QA_ASSISTANT TASK — MVP-BAL v0.3a (bus_section binding + EMERGENCY filtering tests)

ROLE: QA_ASSISTANT  
BRANCH: `feature/circuits-section-qa` (создавай изменения и коммиты только здесь)  
SCOPE (разрешено менять): `tests/*`  
SCOPE (запрещено менять): `db/*`, `calc_core/*`, `tools/*`, `app/*`, `docs/*`, `dwg/*`

## Источник требований

- `docs/contracts/PHASE_BALANCE_V0_1.md` (база)
- `docs/contracts/PHASE_BALANCE_V0_3A.md` (v0.3a)

## Предпосылки (после merge db+calc+ui в main)

- В БД есть `circuits.phase` и `panel_phase_balance`
- В БД есть `circuits.bus_section_id`
- В `calc_core` есть `phase_balance` и экспорт включает `phase`
- UI добавляет кнопки/таблицы (не тестируем UI напрямую, только smoke/инварианты)

## Что нужно сделать (обязательно)

### 0) Migration test: circuits.bus_section_id (обязательно)

Добавить тест, который:

- накатывает миграции на пустую БД
- проверяет, что в `circuits` появился столбец `bus_section_id`

### 1) Тест warnings auto-clear (обязательно)

Обновить/добавить тест (например `tests/test_phase_balance_warnings.py`), который:

- создаёт 1Ф цепь с `phase_source='MANUAL'` и невалидной `phase` (NULL/\"L4\")
- запускает `calc_phase_balance(..., respect_manual=True)`
- проверяет:
  - `panel_phase_balance.invalid_manual_count > 0`
  - `panel_phase_balance.warnings_json` не пуст
  - суммы `i_l1/i_l2/i_l3` НЕ включают ток этой цепи
- затем исправляет фазу (например `phase='L1'` при `phase_source='MANUAL'`) и повторно запускает calc
- проверяет авто-очистку:
  - `invalid_manual_count == 0`
  - `warnings_json IS NULL`

### 2) Тест DB constraint (обязательно)

Добавить тест (например `tests/test_phase_balance_db_constraints.py`), который:

- пытается установить `circuits.phase='L4'` и ожидает `sqlite3.IntegrityError`
- пытается установить `circuits.phase_source='HACK'` и ожидает `sqlite3.IntegrityError`
- пытается вставить `panel_phase_balance.mode='RESERVE'` и ожидает `sqlite3.IntegrityError`

### 3) Тест экспорта phase (обязательно)

Добавить тест (например `tests/test_phase_balance_export.py`), который:

- создаёт tmp SQLite
- накатывает миграции
- вставляет минимум данных, необходимых для `calc_core.export_payload.build_payload`:
  - `panels`
  - `rtm_panel_calc` (обязателен для payload)
  - хотя бы одну 1Ф цепь `circuits` с `phase='L2'`
- вызывает `build_payload(conn, panel_id)`
- проверяет, что `payload["circuits"][0]["phase"] == "L2"`

## Acceptance criteria

- `pytest -q` зелёный.
- Добавлены тесты: migration bus_section_id + EMERGENCY filtering + warnings auto-clear + ограничения БД + экспорт phase.

## Git workflow (обязательно)

1) `git checkout -b feature/circuits-section-qa` (или `git checkout feature/circuits-section-qa`)
2) Правки только в `tests/*`
3) `git add tests`
4) `git commit -m "test: add circuits section binding coverage"`

