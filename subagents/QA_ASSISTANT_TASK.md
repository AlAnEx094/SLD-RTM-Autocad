# QA_ASSISTANT TASK — Phase Balance v0.1 (tests)

ROLE: QA_ASSISTANT  
BRANCH: `feature/phase-balance-qa` (создавай изменения и коммиты только здесь)  
SCOPE (разрешено менять): `tests/*`  
SCOPE (запрещено менять): `db/*`, `calc_core/*`, `tools/*`, `app/*`, `docs/*`, `dwg/*`

## Источник требований

- `docs/contracts/PHASE_BALANCE_V0_1.md`

## Предпосылки (после merge db+calc+ui в main)

- В БД есть `circuits.phase` и `panel_phase_balance`
- В `calc_core` есть `phase_balance` и экспорт включает `phase`
- UI добавляет кнопки/таблицы (не тестируем UI напрямую, только smoke/инварианты)

## Что нужно сделать (обязательно)

### 1) Тест алгоритма балансировки (обязательно)

Добавить тест (например `tests/test_phase_balance_algorithm.py`), который:

- создаёт временную SQLite БД (tmp file)
- накатывает миграции через `tools.run_calc.ensure_migrations`
- вставляет:
  - `panels` (system_type может быть 1PH или 3PH — не критично)
  - несколько `circuits` с `phases=1` и разными `i_calc_a`
- вызывает `calc_core.phase_balance.balance_panel(...)`
- проверяет:
  - у всех 1Ф цепей `circuits.phase IN ('L1','L2','L3')`
  - `panel_phase_balance` создан и содержит численные `i_l1/i_l2/i_l3/unbalance_pct`
  - детерминизм: повторный вызов при неизменном входе не меняет результат (или меняет только `updated_at`)

### 2) Тест DB constraint (обязательно)

Добавить тест (например `tests/test_phase_balance_db_constraints.py`), который:

- пытается установить `circuits.phase='L4'` и ожидает `sqlite3.IntegrityError`
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
- Добавлены тесты: алгоритм + ограничения БД + экспорт phase.

## Git workflow (обязательно)

1) `git checkout -b feature/phase-balance-qa` (или `git checkout feature/phase-balance-qa`)
2) Правки только в `tests/*`
3) `git add tests`
4) `git commit -m "test: add phase balance coverage"`

