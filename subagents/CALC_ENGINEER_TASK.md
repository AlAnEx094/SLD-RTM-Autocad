# CALC_ENGINEER TASK — MVP-BAL v0.3a (EMERGENCY filtering by bus sections)

ROLE: CALC_ENGINEER  
BRANCH: `feature/circuits-section-calc` (создавай изменения и коммиты только здесь)  
SCOPE (разрешено менять): `calc_core/*`, `tools/*`, `dwg/*`  
SCOPE (запрещено менять): `db/*`, `tests/*`, `app/*`

## Источник требований

- `docs/contracts/PHASE_BALANCE_V0_1.md` (база)
- `docs/contracts/PHASE_BALANCE_V0_3A.md` (v0.3a additions)

## Предпосылки (в main после DB merge)

DB уже содержит:

- `circuits.phase` (L1/L2/L3)
- `circuits.phase_source` (AUTO/MANUAL)
- `circuits.bus_section_id` (nullable FK -> bus_sections.id)
- `panel_phase_balance(panel_id, mode, i_l1, i_l2, i_l3, unbalance_pct, updated_at, invalid_manual_count, warnings_json)`

## Цель (обязательно)

### 1) Обновить алгоритм в `calc_core/phase_balance.py` (обязательно)

Добавить модуль:

- `calc_core/phase_balance.py`

API (норма, но можно эквивалентно):

- `calc_phase_balance(conn: sqlite3.Connection, panel_id: str, *, mode: str = \"NORMAL\", respect_manual: bool = True) -> int`

Норматив:

- NORMAL: взять 1Ф цепи `circuits.phases = 1` для `panel_id` (как раньше)
- EMERGENCY (v0.3a): минимальная “реальная” фильтрация:
  - определить `active_emergency_sections` как множество `bus_section_id`, где существует
    `section_calc(panel_id=?, mode='EMERGENCY')` и `sp_kva > 0 OR i_a > 0`
  - если `active_emergency_sections` не пуст:
    - включать в балансировку только 1Ф цепи с `circuits.bus_section_id IN active_emergency_sections`
  - иначе (fallback):
    - включать все 1Ф цепи (как в NORMAL)
    - добавить persisted warning в `warnings_json` с причиной `EMERGENCY_SECTIONS_NOT_COMPUTED`
- ток цепи \(I\): предпочесть `circuit_calc.i_calc_a` если есть, иначе `circuits.i_calc_a`
- если `respect_manual=True`:
  - исключить из переназначения цепи `circuits.phase_source='MANUAL'`
  - сохранить их текущую `circuits.phase`
  - если `phase` невалиден (`NULL` или не `L1|L2|L3`):
    - НЕ включать ток в суммы
    - увеличивать `invalid_manual_count`
    - добавлять warning-объект в список `warnings_json`
- greedy bin-packing для остальных:
  - сортировка по `I` по убыванию (tie-breaker: `circuits.id`)
  - назначать фазу с минимальной суммой
- записать назначения в `circuits.phase`
- записать агрегат в `panel_phase_balance` (upsert по `(panel_id, mode)`), `updated_at=datetime('now')`
- `unbalance_pct` по формуле из контракта
- persist:
  - `invalid_manual_count`
  - `warnings_json` (JSON array)

#### v0.2: warnings auto-clear (non-sticky)

Норматив:

- если в текущем запуске **нет** invalid MANUAL phases:
  - upsert должен записать `invalid_manual_count=0`
  - upsert должен записать `warnings_json=NULL`

Это должно очищать прошлые предупреждения после исправления данных.

### 2) CLI `tools/run_calc.py` (без новых флагов)

Добавить флаги:

- `--calc-phase-balance` (bool): выполнить балансировку фаз
- `--pb-mode NORMAL|EMERGENCY` (default: NORMAL): режим записи в `panel_phase_balance`
- флаги остаются как в v0.1.1 (`--no-respect-manual-phases` уже есть); новых не добавлять без необходимости

CLI должен:

- применять миграции (как сейчас)
- запускать фазную балансировку без зависимости от UI

### 3) Экспорт: phase_source в JSON payload (рекомендуется)

#### A) JSON payload

В `calc_core/export_payload.py` добавить в `payload.circuits[]` поле:

- `phase`: `"L1"|"L2"|"L3"|null`
- `phase_source`: `"AUTO"|"MANUAL"|null` (если колонка существует)
- (опционально) `warnings` не экспортируем в payload v0.4 (UI читает из БД)

#### B) CSV attrs mapping

Обновить `dwg/mapping_v0_5.yaml` (или актуальный mapping проекта), чтобы в `circuits.attributes` появился атрибут,
указывающий на путь `phase`.

Важно:

- экспорт **не запускает расчёты**; он только читает БД
- если `circuits.phase` NULL → в CSV/JSON это должно становиться пустой строкой / `null`

## Acceptance criteria

- `tools/run_calc.py --calc-phase-balance --pb-mode NORMAL` записывает `circuits.phase` и `panel_phase_balance`.
- Экспорт JSON/CSV включает `phase` для цепей.
- `pytest -q` остаётся зелёным (тесты добавит QA).

## Git workflow (обязательно)

1) `git checkout -b feature/circuits-section-calc` (или `git checkout feature/circuits-section-calc`)
2) Правки только в `calc_core/*`, `tools/*`, `dwg/*`
3) `git add calc_core tools dwg`
4) `git commit -m "calc: filter phase balance circuits in EMERGENCY"`

