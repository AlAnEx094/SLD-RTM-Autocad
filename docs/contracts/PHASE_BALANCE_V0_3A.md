# PHASE_BALANCE v0.3a — pb-mode EMERGENCY with bus-section binding (MVP-BAL)

Этот документ фиксирует расширение контракта балансировки фаз для **однофазных (1Φ) цепей**,
чтобы `pb-mode=EMERGENCY` был честным и мог фильтровать цепи по активным аварийным секциям шин.

Основа (v0.1 + v0.2) остаётся в `docs/contracts/PHASE_BALANCE_V0_1.md`.

## 1) Motivation / почему нужен v0.3a

До v0.3a:

- `pb-mode` влияло только на **storage/display** в `panel_phase_balance(panel_id, mode, ...)`.
- `circuits.phase` не является mode-specific.
- у `circuits` не было привязки к секции шин → невозможно было фильтровать “аварийные” цепи.

v0.3a вводит `circuits.bus_section_id`, чтобы сделать минимально рабочую модель:

- в `EMERGENCY` включаются только цепи, относящиеся к **активным аварийным секциям**.

## 2) DB changes (v0.3a)

Добавляется столбец:

- `circuits.bus_section_id TEXT NULL REFERENCES bus_sections(id) ON DELETE SET NULL`

Семантика:

- `NULL` означает “цепь не привязана к секции”.
- Привязка требуется для корректного `pb-mode=EMERGENCY`.

## 3) pb-mode semantics (v0.3a)

### 3.1 NORMAL

`mode='NORMAL'` — поведение как раньше (MVP-BAL v0.1/v0.2):

- в балансировку включаются **все 1Φ цепи панели** (`circuits.phases=1`),
  плюс действуют правила `phase_source/respect_manual`.

### 3.2 EMERGENCY (real filtering, minimal)

`mode='EMERGENCY'` — v0.3a добавляет **фильтрацию кандидатов** по активным аварийным секциям.

Алгоритм выбора активных аварийных секций (definition for v0.3a):

- взять секции `bus_section_id`, для которых существует строка:
  - `section_calc.panel_id = <panel_id>`
  - `section_calc.mode = 'EMERGENCY'`
  - и \(section\_calc.sp\_kva > 0\) **или** \(section\_calc.i\_a > 0\)

Тогда:

- в балансировку включаются только 1Φ цепи, у которых:
  - `circuits.phases = 1`
  - `circuits.bus_section_id` ∈ `active_emergency_sections`

Fallback (обязательное поведение):

- если **активные аварийные секции не определены** (нет строк `section_calc` для `EMERGENCY`
  или все нагрузки нулевые), то балансировка:
  - **не может быть реальной аварийной**
  - должна включить **все 1Φ цепи** как fallback
  - и должна зафиксировать предупреждение в `panel_phase_balance.warnings_json`
    с причиной `EMERGENCY_SECTIONS_NOT_COMPUTED`.

Ограничения (честно):

- если часть 1Φ цепей имеет `circuits.bus_section_id IS NULL`, то в `EMERGENCY`
  они будут исключены фильтром (при наличии active emergency sections).
- UI обязан подсвечивать это предупреждением (см. UI notes).

## 4) Warnings (persisted) and auto-clear

`panel_phase_balance` содержит:

- `invalid_manual_count` и `warnings_json` (v0.1.2)

Норматив v0.3a:

- `warnings_json` может содержать как circuit-level warnings (например `MANUAL_INVALID_PHASE`),
  так и panel-level warnings (например `EMERGENCY_SECTIONS_NOT_COMPUTED`).
- Warnings auto-clear сохраняется (v0.2):
  - если по результату текущего запуска warnings отсутствуют → записать
    `invalid_manual_count=0` и `warnings_json=NULL` (не “залипает”).

## 5) UI notes (non-normative, acceptance)

Минимальные требования UI v0.3a:

- editable `circuits.bus_section_id` (dropdown по `bus_sections` текущего щита)
- при `pb-mode=EMERGENCY`:
  - warning если среди 1Φ цепей есть `bus_section_id IS NULL`
  - warning если аварийные секции не рассчитаны (fallback использован)

