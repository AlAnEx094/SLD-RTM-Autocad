# CALC_ENGINEER TASK — Phase Balance v0.1.1 (respect MANUAL)

ROLE: CALC_ENGINEER  
BRANCH: `feature/phase-source-calc` (создавай изменения и коммиты только здесь)  
SCOPE (разрешено менять): `calc_core/*`, `tools/*`, `dwg/*`  
SCOPE (запрещено менять): `db/*`, `tests/*`, `app/*`

## Источник требований

- `docs/contracts/PHASE_BALANCE_V0_1.md`

## Предпосылки (в main после DB merge)

DB уже содержит:

- `circuits.phase` (L1/L2/L3)
- `circuits.phase_source` (AUTO/MANUAL)
- `panel_phase_balance(panel_id, mode, i_l1, i_l2, i_l3, unbalance_pct, updated_at)`

## Цель (обязательно)

### 1) Обновить алгоритм в `calc_core/phase_balance.py`

Добавить модуль:

- `calc_core/phase_balance.py`

API (норма, но можно эквивалентно):

- `calc_phase_balance(conn: sqlite3.Connection, panel_id: str, *, mode: str = \"NORMAL\", respect_manual: bool = True) -> int`

Норматив:

- взять 1Ф цепи `circuits.phases = 1` для `panel_id`
- ток цепи \(I\): предпочесть `circuit_calc.i_calc_a` если есть, иначе `circuits.i_calc_a`
- если `respect_manual=True`:
  - исключить из переназначения цепи `circuits.phase_source='MANUAL'`
  - сохранить их текущую `circuits.phase`
  - учесть их ток в суммах фаз, если фаза валидна (`L1|L2|L3`)
- greedy bin-packing для остальных:
  - сортировка по `I` по убыванию (tie-breaker: `circuits.id`)
  - назначать фазу с минимальной суммой
- записать назначения в `circuits.phase`
- записать агрегат в `panel_phase_balance` (upsert по `(panel_id, mode)`), `updated_at=datetime('now')`
- `unbalance_pct` по формуле из контракта

### 2) Расширить CLI `tools/run_calc.py`

Добавить флаги:

- `--calc-phase-balance` (bool): выполнить балансировку фаз
- `--pb-mode NORMAL|EMERGENCY` (default: NORMAL): режим записи в `panel_phase_balance`
- флаг для отключения защиты manual фаз (например `--no-respect-manual-phases`), который передаёт `respect_manual=False`

CLI должен:

- применять миграции (как сейчас)
- запускать фазную балансировку без зависимости от UI

### 3) Экспорт: phase_source в JSON payload (рекомендуется)

#### A) JSON payload

В `calc_core/export_payload.py` добавить в `payload.circuits[]` поле:

- `phase`: `"L1"|"L2"|"L3"|null`
- `phase_source`: `"AUTO"|"MANUAL"|null` (если колонка существует)

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

1) `git checkout -b feature/phase-source-calc` (или `git checkout feature/phase-source-calc`)
2) Правки только в `calc_core/*`, `tools/*`, `dwg/*`
3) `git add calc_core tools dwg`
4) `git commit -m "calc: respect MANUAL phase assignments"`

