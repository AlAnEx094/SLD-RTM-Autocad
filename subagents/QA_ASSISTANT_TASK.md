# QA_ASSISTANT TASK — feature/qa-tests (MVP-0.2 Voltage Drop)

ROLE: QA_ASSISTANT  
BRANCH: `feature/qa-tests` (создать изменения и коммиты только здесь)  
SCOPE (разрешено менять): `tests/*`  
SCOPE (запрещено менять): `db/*`, `calc_core/*`, `tools/*`, `docs/*`, `cad_adapter/*`

## Контекст

MVP-0.2 добавляет расчёт падения напряжения ΔU и подбор минимального сечения по ΔU.
DB изменения (circuits/circuit_calc/cable_sections + лимиты в panels) делает DB_ENGINEER,
CalcCore (`calc_core/voltage_drop.py` + `tools/run_calc.py --calc-du`) делает CALC_ENGINEER.

Твоя задача — добавить контрактные тесты, которые фиксируют:
- учёт `X` и `sinφ`
- правило `b` (1/2) для 1PH/3PH/NORMAL/FULL_UNBALANCED
- правило увеличения лимита при `length_m > 100`
- корректный выбор **минимального** `S` из `cable_sections`

## Что нужно сделать

### 1) `tests/test_voltage_drop.py` (обязательно)

Покрыть кейсы:

1) **1PH Cu**:
   - при увеличении `S` `du_pct` уменьшается
   - `select_min_section_by_du` выбирает минимальное `S`, удовлетворяющее лимиту

2) **3PH NORMAL**:
   - при прочих равных `b=1` даёт `du_v` в 2 раза меньше, чем `b=2`
   - проверить через сравнение двух circuits: (3PH NORMAL) vs (3PH FULL_UNBALANCED) с одинаковыми входами

3) **FULL_UNBALANCED**:
   - `phases=3` + `unbalance_mode='FULL_UNBALANCED'` → `b=2` (как 1PH)

4) **length > 100 m**:
   - лимит увеличивается на:
     - `add_pct = min(0.005 * (L - 100), 0.5)`
     - `effective = base + add_pct`
   - и это влияет на выбранное `S` (подготовь данные так, чтобы на `L<=100` одно S не проходило,
     а на `L>100` стало проходить, либо наоборот — главное, чтобы тест ловил правило).

Важно:
- Не выдумывай численные “ожидания” ΔU из головы. Для проверок используй:
  - монотонность (du падает при росте S)
  - отношение (b=1 vs b=2 → ровно ×2)
  - сравнение выбранных S при разных лимитах/длинах

### 2) Smoke test `tests/test_voltage_drop_smoke.py` (или расширить существующий smoke) (обязательно)

Минимальный сквозной сценарий:

- создать временную SQLite
- применить миграции `0001_init.sql` + `0002_circuits.sql`
- применить seed `seed_cable_sections.sql`
- вставить:
  - `panels` (обязательно `u_ph_v`, и лимиты ΔU пусть будут дефолтные или явные)
  - `circuits` (как минимум 1 строка)
- вызвать CLI:
  - `python tools/run_calc.py --db <tmp> --calc-du --panel-id <id>`
- проверить:
  - строка в `circuit_calc` создана
  - `du_limit_pct` записан и соответствует `effective_du_limit`
  - `s_mm2_selected` заполнен

## Git workflow

1) `git checkout -b feature/qa-tests` (или `git checkout feature/qa-tests`)
2) Правки только в `tests/*`
3) `git add tests`
4) `git commit -m "test: add voltage drop contract tests (MVP-0.2)"`

## Проверка

- `pytest -q`

