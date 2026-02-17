# PHASE_BALANCE v0.1 — балансировка фаз однофазных цепей (MVP-BAL)

Этот документ фиксирует **жёсткий контракт** фазной балансировки для **однофазных (1Φ) цепей**:

- присвоение `phase=L1/L2/L3` каждой 1Φ цепи
- расчёт сумм токов по фазам и процента неравномерности
- **DB = истина**: фазы и агрегат баланса хранятся в SQLite и используются UI/экспортом

## 1) Scope / что входит

Входит:

- Балансировка **только 1Φ цепей**: `circuits.phases = 1`
- Персистентные результаты:
  - `circuits.phase` (L1/L2/L3)
  - `panel_phase_balance` (суммы токов по фазам + `unbalance_pct`)
- Экспорт:
  - JSON payload (DWG payload v0.4): добавляется `circuits[].phase`
  - CSV attrs (DWG mapping v0.5): добавляется атрибут цепи, который читает `phase`

Не входит (v0.1):

- учёт разных токов по режимам `NORMAL/EMERGENCY` (в v0.1 баланс строится по одному набору токов)
- балансировка 3Φ цепей (`circuits.phases = 3`)
- “магия” в UI: UI отображает то, что записано в БД

## 2) Глоссарий

- **Щит / Panel**: `panels`
- **Цепь / Circuit**: `circuits`
- **Фаза / Phase**: `L1`, `L2`, `L3` (строковый код в БД)
- **Режим расчёта / Calculation mode**: `NORMAL`, `EMERGENCY` (для будущей совместимости; v0.1 пишет по запрошенному mode)

## 3) Источники данных (SQLite)

### 3.1 Вход (таблицы)

- `circuits(id, panel_id, phases, i_calc_a, ...)`
- `circuit_calc(circuit_id, i_calc_a, ...)` (опционально; если есть, может использоваться как “уточнённый” ток)

Требования к входу:

- `circuits.phases` ∈ {1, 3}
- для `circuits.phases = 1` ток \(I\) должен быть числом и \(I \ge 0\)

### 3.2 Выход (таблицы, persisted)

#### A) `circuits.phase`

Новый столбец:

- `circuits.phase TEXT NULL CHECK (phase IN ('L1','L2','L3'))`

Семантика:

- **только для 1Φ**: если `circuits.phases != 1`, поле может быть `NULL`
- после успешного запуска балансировки для панели все 1Φ цепи панели должны иметь `phase IN ('L1','L2','L3')`

#### B) `panel_phase_balance`

Новая таблица:

`panel_phase_balance(panel_id, mode, i_l1, i_l2, i_l3, unbalance_pct, updated_at)`

Рекомендуемые ограничения:

- `mode TEXT NOT NULL CHECK(mode IN ('NORMAL','EMERGENCY'))`
- `PRIMARY KEY(panel_id, mode)`

Семантика:

- значения `i_l1/i_l2/i_l3` — суммы токов 1Φ цепей по фазам (А)
- `unbalance_pct` — процент неравномерности (см. формулу ниже)
- `updated_at` — `datetime('now')` при upsert

## 4) Нормативная математика

### 4.1 Ток цепи \(I\)

Для каждой цепи `c` (только `c.phases = 1`) определяется ток \(I_c\):

- если существует `circuit_calc` для этой цепи: \(I_c = circuit\_calc.i\_calc\_a\)
- иначе: \(I_c = circuits.i\_calc\_a\)

Требование: \(I_c \ge 0\). Нарушение — ошибка (не “чинить”).

### 4.2 Суммы токов по фазам

\[
I_{L1} = \sum_{c \in C_{L1}} I_c,\quad
I_{L2} = \sum_{c \in C_{L2}} I_c,\quad
I_{L3} = \sum_{c \in C_{L3}} I_c
\]

где \(C_{Lx}\) — множество 1Φ цепей панели, назначенных на фазу \(Lx\).

### 4.3 Неравномерность, %

Определения:

\[
I_{max} = \max(I_{L1}, I_{L2}, I_{L3})
\]
\[
I_{avg} = \frac{I_{L1} + I_{L2} + I_{L3}}{3}
\]

Тогда:

- если \(I_{avg} = 0\) → `unbalance_pct = 0`
- иначе:

\[
unbalance\_{pct} = 100 \cdot \frac{I_{max} - I_{avg}}{I_{avg}}
\]

## 5) Алгоритм балансировки (normative)

Цель: минимизировать перекос токов между фазами простым и детерминированным методом.

Метод (greedy bin-packing):

1) Для заданного `panel_id` выбрать все цепи:
   - `circuits.panel_id = panel_id`
   - `circuits.phases = 1`
2) Для каждой цепи вычислить \(I_c\) (см. 4.1).
3) Отсортировать цепи по \(I_c\) по убыванию, tie-breaker: `circuits.id` (стабильность).
4) Инициализировать суммы фаз:
   - `sum[L1]=0`, `sum[L2]=0`, `sum[L3]=0`
5) Для каждой цепи в отсортированном списке:
   - назначить фазу с **минимальной текущей суммой** `sum[Lx]`
   - записать назначение в `circuits.phase`
   - увеличить `sum[chosen] += I_c`
6) После назначения всех цепей:
   - вычислить `i_l1/i_l2/i_l3` и `unbalance_pct` (см. 4.2–4.3)
   - upsert в `panel_phase_balance(panel_id, mode, ...)` для заданного `mode`

Примечание (про ручные правки в UI):

- UI может редактировать `circuits.phase` в `EDIT`.
- Запуск балансировки (calc) **перезаписывает** назначения для 1Φ цепей панели по алгоритму выше.

## 6) CLI / запуск расчёта

`tools/run_calc.py` расширяется флагом:

- `--calc-phase-balance` — выполнить фазную балансировку после базовых расчётов
- `--pb-mode {NORMAL|EMERGENCY}` — режим записи в `panel_phase_balance` (default: `NORMAL`)

CLI не обязан запускать ΔU; ток \(I_c\) берётся из `circuits.i_calc_a` (или `circuit_calc.i_calc_a` если есть).

## 7) Экспорт

### 7.1 JSON payload (DWG payload v0.4)

В `calc_core.export_payload.build_payload` для каждой цепи добавить поле:

- `payload.circuits[].phase`: `"L1"|"L2"|"L3"|null`

Правило:

- если `circuits.phases != 1` → `phase = null`
- если `circuits.phases = 1` и `circuits.phase` пустой → `phase = null` (до балансировки)

### 7.2 CSV attrs (DWG mapping v0.5)

В mapping для `circuits.attributes` должен появиться атрибут, который указывает на путь:

- `phase`

Форматирование: строка без преобразований.

## 8) Совместимость / existing tables

В схеме уже существует `panel_phase_calc (ia_a, ib_a, ic_a, ...)` — это отдельный исторический расчёт по RTM (A/B/C).
Контракт PHASE_BALANCE v0.1 **не изменяет** и **не использует** `panel_phase_calc`.

## 9) Acceptance criteria (DoD)

- В БД присутствуют:
  - `circuits.phase` с CHECK на `L1/L2/L3`
  - `panel_phase_balance` с `PRIMARY KEY(panel_id, mode)`
- Алгоритм присваивает фазу всем 1Φ цепям панели и пишет агрегат.
- UI показывает фазы и итоги, а запуск балансировки обновляет БД.
- Экспорт JSON/CSV включает `phase`.

---

## 10) v0.2 additions (MVP-BAL v0.2)

### 10.1 pb-mode semantics (UI selector)

В UI появляется selector `pb-mode` = `NORMAL|EMERGENCY`.

В текущей реализации (MVP-BAL v0.2):

- `pb-mode` влияет **только** на:
  - в какую строку `panel_phase_balance(panel_id, mode, ...)` будет записан агрегат
  - какую строку `panel_phase_balance` UI отображает
- `pb-mode` **не меняет набор цепей** и **не фильтрует** входные данные: алгоритм балансировки работает по всем 1Φ цепям панели.

Важно (ограничение модели данных):

- назначение фазы хранится в `circuits.phase` (одно поле на цепь), то есть **фаза не является mode-specific**.
- поэтому запуск балансировки в `EMERGENCY` пересчитает те же `circuits.phase`, что и в `NORMAL`, и запишет агрегат в другую строку `panel_phase_balance`.

### 10.2 phase_source (MANUAL protection) and invalid MANUAL warnings

В ветке v0.1.1 введено `circuits.phase_source`:

- `AUTO` — назначено алгоритмом
- `MANUAL` — назначено пользователем и по умолчанию защищено от перезаписи

В v0.1.2 добавлены persisted warnings в `panel_phase_balance`:

- `invalid_manual_count` — количество 1Φ цепей с `phase_source='MANUAL'` и невалидной/пустой `phase`
- `warnings_json` — JSON array с деталями проблемных цепей

Норматив (v0.2):

- 1Φ цепи с `phase_source='MANUAL'` и невалидной `phase`:
  - **не включаются** в суммы `i_l1/i_l2/i_l3`
  - учитываются в `invalid_manual_count`
  - перечисляются в `warnings_json`

### 10.3 Warnings auto-clear (no stale warnings)

Норматив (v0.2):

- если в текущем запуске балансировки **нет** invalid MANUAL phases:
  - `invalid_manual_count` должен быть записан как `0`
  - `warnings_json` должен быть записан как `NULL`

Это гарантирует, что предупреждения не “залипают” после исправления данных.

