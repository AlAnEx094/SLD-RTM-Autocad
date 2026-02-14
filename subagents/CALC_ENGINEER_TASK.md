# CALC_ENGINEER TASK — feature/calc-core

ROLE: CALC_ENGINEER  
BRANCH: `feature/calc-core` (создать изменения и коммиты только здесь)  
SCOPE (разрешено менять): `calc_core/*` и `tools/*`  
SCOPE (запрещено менять): `db/*`, `tests/*`, `docs/*`, `cad_adapter/*`

## Контекст (baseline)

Сейчас есть несогласованность: `calc_core/rtm_f636.py` и `tools/run_calc.py` обращаются к таблицам
`rtm_input_rows / calc_runs / rtm_calc_rows`, которых **нет** в актуальной схеме.

Актуальная схема (см. `db/migrations/0001_init.sql`):

- `panels(id, name, system_type('3PH'|'1PH'), u_ll_v, u_ph_v)`
- `rtm_rows(id, panel_id, name, n, pn_kw, ki, cos_phi, tg_phi, phases, phase_mode, phase_fixed, ...)`
- `rtm_row_calc(row_id PK/FK -> rtm_rows.id, pn_total, ki_pn, ki_pn_tg, n_pn2)`
- `rtm_panel_calc(panel_id PK/FK -> panels.id, sum_pn, sum_ki_pn, sum_ki_pn_tg, sum_np2, ne, kr, pp_kw, qp_kvar, sp_kva, ip_a, updated_at)`
- `panel_phase_calc(panel_id PK/FK -> panels.id, ...)` (пока может оставаться пустой, если phase_balance ещё не реализован)
- `kr_table(ne, ki, kr, source)` (Kr lookup по контракту)

## Цель

Привести `calc_core` и `tools/run_calc.py` к **актуальной SQLite схеме**, не меняя контрактов:

- **Kr контракт** НЕ менять: clamp Ki, ne_tab вверх, линейная интерполяция по Ki в строке `ne_tab`, таблица в SQLite.
- **PhaseBalance контракт** НЕ менять (если файла/логики нет — не придумывать; только оставить совместимость по таблицам).

## Что нужно сделать

### 1) Переписать расчёт RTM на таблицы `rtm_rows/rtm_row_calc/rtm_panel_calc`

В `calc_core/rtm_f636.py`:

- читать входные строки из `rtm_rows` по `panel_id`
- записывать:
  - per-row расчёт в `rtm_row_calc` (upsert по `row_id`)
  - итоги по щиту в `rtm_panel_calc` (upsert по `panel_id`, обновляя `updated_at`)

Минимальный набор вычислений для MVP (консервативно):

- `pn_total` = `n * pn_kw`
- `ki_pn` = `ki * pn_total`
- `ki_pn_tg` = `ki_pn * tg_phi`, где:
  - если `tg_phi` задан, использовать его
  - иначе если `cos_phi` задан, вычислить `tg_phi = tan(acos(cos_phi))`
  - иначе `tg_phi = 0` (консервативно)
- `n_pn2` = `n * pn_kw * pn_kw`

Итоги:

- `sum_pn` = Σ(pn_total)
- `sum_ki_pn` = Σ(ki_pn)
- `sum_ki_pn_tg` = Σ(ki_pn_tg)
- `sum_np2` = Σ(n_pn2)
- `ne` = (sum_pn ** 2) / sum_np2  (если sum_np2 > 0, иначе ошибка)
- `ki_group` = sum_ki_pn / sum_pn (если sum_pn > 0, иначе ошибка)
- `kr` = `get_kr(db_path, ne, ki_group)` по контракту Kr
- `pp_kw` = `kr * sum_ki_pn`
- `qp_kvar` = `kr * sum_ki_pn_tg`
- `sp_kva` = sqrt(pp_kw**2 + qp_kvar**2)
- `ip_a`:
  - для `panels.system_type='3PH'`: \( I = S*1000 / (\sqrt{3} * U_{LL}) \) (требует `u_ll_v`)
  - для `panels.system_type='1PH'`: \( I = S*1000 / U_{PH} \) (требует `u_ph_v`)

Доп. правило (если применимо в RTM_F636 контракте проекта): `pp_kw >= pn_max`:
- `pn_max` = max(pn_total) по строкам
- если `pp_kw < pn_max`, то `pp_kw = pn_max` (и пересчитать `sp_kva`/`ip_a` по обновлённому `pp_kw`, `qp_kvar` оставить как есть)

### 2) Обновить `tools/run_calc.py`

- Убрать обращения к несуществующим таблицам.
- Создавать демо-данные в `panels` и `rtm_rows` (если в щите нет строк).
  - При вставке `panels` обязательно заполнить `system_type` и соответствующие напряжения:
    - 3PH: `system_type='3PH'`, `u_ll_v=400`, `u_ph_v=230`
  - Для `rtm_rows` выбрать демо‑строки с `phase_mode='NONE'` (пока фазировку не считаем) и `phases=3`.

### 3) Совместимость с `cad_adapter`

Не менять `cad_adapter`, но обеспечить, чтобы после расчёта существовала строка в `rtm_panel_calc` для `panel_id`
(иначе cad_adapter payload будет `null`).

## Acceptance criteria

- Код в `feature/calc-core` не обращается к `rtm_input_rows/calc_runs/rtm_calc_rows`.
- `tools/run_calc.py` создаёт БД (через миграции) и считает один щит, записывая `rtm_row_calc` и `rtm_panel_calc`.
- `python3 -m pytest -q` **пока может падать** (QA починит тесты), но падения не должны быть из‑за SQL таблиц “не существует”.

## Git workflow

1) `git checkout feature/calc-core`
2) Правки только в `calc_core/*` и `tools/*`
3) `git add calc_core tools`
4) `git commit -m "calc: align RTM calc to rtm_rows schema"`

