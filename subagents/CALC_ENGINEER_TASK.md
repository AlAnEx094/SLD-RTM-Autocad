# CALC_ENGINEER TASK — feature/calc-core (MVP-0.2 Voltage Drop / Section selection)

ROLE: CALC_ENGINEER  
BRANCH: `feature/calc-core` (создать изменения и коммиты только здесь)  
SCOPE (разрешено менять): `calc_core/*` и `tools/*`  
SCOPE (запрещено менять): `db/*`, `tests/*`, `docs/*`, `cad_adapter/*`

## Контекст

MVP-0.2 добавляет расчёт падения напряжения ΔU и подбор **минимального** сечения по ΔU
по ГОСТ Р 50571.5.52-2011, Приложение G (справочное).

Жёсткие константы (НЕ выдумывать):
- `rho_Cu = 0.0225` Ом·мм²/м (уже включает 1.25×)
- `rho_Al = 0.036` Ом·мм²/м (уже включает 1.25×)
- `X = 0.08` мОм/м = `0.00008` Ом/м

Принципы:
- ΔU% считать относительно `U0` = `panels.u_ph_v` (фаза‑нейтраль).
- DB=истина: ввод в `circuits`, результаты в `circuit_calc`.
- Никаких изменений в `db/*` (миграции делает DB_ENGINEER).

## Цель

1) Реализовать `calc_core/voltage_drop.py`:
   - вычисление ΔU (В) и ΔU% по формуле Прил. G (с учётом `ρ`, `X`, `cosφ/sinφ`, `b`, длины, I, S)
   - подбор минимального `S` из `cable_sections` так, чтобы `du_pct <= du_limit_pct`
   - запись результата в `circuit_calc` (upsert по `circuit_id`)

2) Расширить `tools/run_calc.py`:
   - опция `--calc-du --panel-id <id>`: считать ΔU по **всем** `circuits` данного `panel_id`

## Контракт расчёта (как реализовать)

### 1) `b` (1/2)

- Если `circuits.phases == 3` и `circuits.unbalance_mode == 'NORMAL'` → `b = 1`
- Иначе → `b = 2`

То есть:
- 1PH всегда `b=2`
- 3PH FULL_UNBALANCED считать как 1PH (`b=2`)

### 2) `sinφ` из `cosφ`

Сделать `sin_phi(cos_phi)`:
- \( \sin\varphi = \sqrt{\max(0, 1 - \cos^2\varphi)} \)
- `cos_phi` должен быть в [0..1] (если вне — raise, не “чинить”)

### 3) Эффективный лимит при длине >100 м

Функция `effective_du_limit(base_limit_pct, length_m)`:
- если `length_m <= 100` → `base_limit_pct`
- иначе:
  - `add_pct = min(0.005 * (length_m - 100), 0.5)`
  - `effective = base_limit_pct + add_pct`

### 4) Формула ΔU (В) по Прил. G (MVP)

Функция `calc_du_v(b, rho, x, L, S, cos_phi, sin_phi, I)`:

- \( \Delta U = b \cdot \left( \rho \cdot \frac{L}{S}\cdot \cos\varphi + x \cdot L \cdot \sin\varphi \right)\cdot I \)

Где:
- `rho` = `RHO_CU` или `RHO_AL` (Ом·мм²/м)
- `x` = `X_PER_M` (Ом/м)
- `L` = `length_m` (м)
- `S` = `s_mm2` (мм²)
- `I` = `i_calc_a` (А)

### 5) ΔU% относительно U0

- `U0` брать из `panels.u_ph_v`
- `du_pct = 100 * du_v / U0`

### 6) Выбор лимита ΔU на панели

База:
- если `circuits.load_kind == 'LIGHTING'` → `panels.du_limit_lighting_pct`
- иначе → `panels.du_limit_other_pct`

Далее:
- `du_limit_pct = effective_du_limit(base, length_m)`

### 7) Подбор минимального сечения

Функция `select_min_section_by_du(conn, circuit_id)` или аналог:

- Получить список `S` из `cable_sections` (по возрастанию).
- Для каждого `S`:
  - посчитать `du_pct`
  - выбрать **первое** `S`, где `du_pct <= du_limit_pct`
- Если ни одно не прошло → выбрать **максимальное** `S` и записать факт (например `method` содержит `NO_SECTION_MEETS_LIMIT`).

### 8) Запись результата

`calc_circuit_du(conn, circuit_id) -> None`:
- читает `circuits` + `panels` по `panel_id`
- пишет `circuit_calc` (upsert), заполняя:
  - `i_calc_a` (как во входе)
  - `du_v`, `du_pct`, `du_limit_pct`, `s_mm2_selected`
  - `method` (например `GOST_R_50571_5_52_2011_APP_G`)
  - `updated_at` (ISO8601 UTC)

## Acceptance criteria

- `calc_core/voltage_drop.py` покрывает случаи 1PH/3PH, NORMAL/FULL_UNBALANCED (через b).
- `tools/run_calc.py --calc-du --panel-id X` создаёт/обновляет `circuit_calc` для всех цепей панели.
- Не изменять `db/*` и существующий RTM расчёт (это другой scope).

## Git workflow

1) `git checkout -b feature/calc-core` (или `git checkout feature/calc-core`)
2) Правки только в `calc_core/*` и `tools/*`
3) `git add calc_core tools`
4) `git commit -m "calc: add voltage drop and section selection (MVP-0.2)"`

