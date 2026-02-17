# QA_ASSISTANT TASK — Phase Balance v0.1.1 (phase_source tests)

ROLE: QA_ASSISTANT  
BRANCH: `feature/phase-source-qa` (создавай изменения и коммиты только здесь)  
SCOPE (разрешено менять): `tests/*`  
SCOPE (запрещено менять): `db/*`, `calc_core/*`, `tools/*`, `app/*`, `docs/*`, `dwg/*`

## Источник требований

- `docs/contracts/PHASE_BALANCE_V0_1.md`

## Предпосылки (после merge db+calc+ui в main)

- В БД есть `circuits.phase` и `panel_phase_balance`
- В `calc_core` есть `phase_balance` и экспорт включает `phase`
- UI добавляет кнопки/таблицы (не тестируем UI напрямую, только smoke/инварианты)

## Что нужно сделать (обязательно)

### 1) Тест respect_manual (обязательно)

Добавить тест (например `tests/test_phase_balance_respect_manual.py`), который:

Сценарии:

- `respect_manual=True` сохраняет фазы цепей с `phase_source='MANUAL'`
- `respect_manual=False` допускает перезапись фаз (детерминированный кейс)

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
- Добавлены тесты: respect_manual true/false + ограничения БД + экспорт phase.

## Git workflow (обязательно)

1) `git checkout -b feature/phase-source-qa` (или `git checkout feature/phase-source-qa`)
2) Правки только в `tests/*`
3) `git add tests`
4) `git commit -m "test: cover respect_manual phase balance"`

