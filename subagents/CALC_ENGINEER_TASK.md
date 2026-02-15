# CALC_ENGINEER TASK — feature/calc-core (MVP-0.4 Export DWG JSON payload)

ROLE: CALC_ENGINEER  
BRANCH: `feature/calc-core` (создать изменения и коммиты только здесь)  
SCOPE (разрешено менять): `calc_core/*` и `tools/*`  
SCOPE (запрещено менять): `db/*`, `tests/*`, `docs/*`, `cad_adapter/*`

## Контекст

MVP-0.4 добавляет экспорт JSON payload для последующей синхронизации с DWG
(без AutoCAD API).

Экспорт **читает только результаты** из SQLite и **не запускает расчёты**.
Источники:
- `rtm_panel_calc` (обязательно)
- `circuit_calc` (опционально по каждой цепи)
- `section_calc` (опционально по секциям/режимам)

## Цель

### 1) CalcCore: `calc_core/export_payload.py`

Добавить модуль и функцию:

- `build_payload(conn, panel_id: str) -> dict`

Payload контракт v0.4 (кратко):
- `version='0.4'`
- `generated_at` ISO8601 (UTC)
- `panel`: данные из `panels` + `rtm_panel_calc` + лимиты ΔU
- `bus_sections`: список секций из `bus_sections` с `modes` из `section_calc` (только существующие строки)
- `circuits`: список цепей из `circuits` + `calc` из `circuit_calc`
- `dwg_contract`: `{"mapping_version":"0.4","block_guid_attr":"GUID"}`

Правила:
- Если `rtm_panel_calc` отсутствует для `panel_id` → ошибка с понятным текстом (`ValueError`).
- Если `circuit_calc` отсутствует для цепи → цепь всё равно в payload, но `calc.status='NO_CALC'` и поля расчёта `null`
  (минимум `du_v/du_pct/du_limit_pct/s_mm2_selected`; `i_calc_a` можно брать из `circuits.i_calc_a`).
- Для `section_calc`: включать только секции, что есть в `bus_sections`; внутри `modes` включать только те режимы, для которых есть строка.

### 2) Tools: `tools/export_payload.py`

CLI, который **не запускает расчёты**:

- args: `--db`, `--panel-id`, `--out <path>`
- подключение к SQLite read-only (`mode=ro` через URI)
- вызвать `build_payload` и записать pretty JSON:
  - `ensure_ascii=False`, `indent=2`

### 3) Docs: контракт payload

Добавить `docs/contracts/DWG_PAYLOAD_V0_4.md`:
- перечисление полей
- правила nullability/ошибок (`NO_CALC`, отсутствие `rtm_panel_calc`)
- минимальный пример payload

## Acceptance criteria

- `tools/export_payload.py` не пишет в БД и не запускает расчёты.
- Payload соответствует контракту v0.4, включая `NO_CALC` поведение.
- Существующие CLI (`run_calc.py`, `export_results.py`) не ломаются.

## Git workflow

1) `git checkout -b feature/calc-core` (или `git checkout feature/calc-core`)
2) Правки только в `calc_core/*` и `tools/*`
3) `git add calc_core tools`
4) `git commit -m "calc: add export payload v0.4 for DWG sync"`

