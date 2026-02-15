# DWG_PAYLOAD v0.4 — контракт JSON payload (DB → DWG)

Этот документ фиксирует контракт экспортируемого JSON payload для последующей синхронизации DWG.
В MVP-0.4 **AutoCAD API не используется**: экспорт читает **только результаты** из SQLite.

## Общие правила

- Экспорт **не запускает расчёты** и **не модифицирует** БД (read-only).
- Если обязательные результаты отсутствуют — экспорт завершаетcя ошибкой.
- Все идентификаторы (`panel_id`, `bus_section_id`, `circuit_id`) — GUID строкового типа (`TEXT` в SQLite).

## Обязательные источники данных

- `panels` (метаданные щита)
- `rtm_panel_calc` (итоги РТМ по щиту) — **обязательно**

## Опциональные источники данных

- `bus_sections` + `section_calc` (агрегация по секциям)
- `circuits` + `circuit_calc` (ΔU/подбор сечения)

## Payload schema (v0.4)

`payload`:

```json
{
  "version": "0.4",
  "generated_at": "2026-02-15T12:34:56+00:00",
  "panel": {
    "panel_id": "...",
    "name": "...",
    "system_type": "1PH|3PH",
    "u_ll_v": 400.0,
    "u_ph_v": 230.0,
    "du_limits": { "lighting_pct": 3.0, "other_pct": 5.0 },
    "rtm": { "pp_kw": 0.0, "qp_kvar": 0.0, "sp_kva": 0.0, "ip_a": 0.0, "kr": 0.0, "ne": 0.0 }
  },
  "bus_sections": [
    {
      "bus_section_id": "...",
      "name": "...",
      "modes": {
        "NORMAL": { "pp_kw": 0.0, "qp_kvar": 0.0, "sp_kva": 0.0, "ip_a": 0.0 },
        "RESERVE": { "pp_kw": 0.0, "qp_kvar": 0.0, "sp_kva": 0.0, "ip_a": 0.0 }
      }
    }
  ],
  "circuits": [
    {
      "circuit_id": "...",
      "name": "…",
      "phases": 1,
      "length_m": 10.0,
      "material": "CU|AL",
      "cos_phi": 0.9,
      "load_kind": "LIGHTING|OTHER",
      "calc": {
        "status": "OK|NO_CALC",
        "i_calc_a": 10.0,
        "du_v": 1.23,
        "du_pct": 0.53,
        "du_limit_pct": 3.0,
        "s_mm2_selected": 2.5
      }
    }
  ],
  "dwg_contract": { "mapping_version": "0.4", "block_guid_attr": "GUID" }
}
```

## Nullability / ошибки

### `rtm_panel_calc` отсутствует

- Если для `panel_id` нет строки в `rtm_panel_calc` → экспорт **ошибка** (обязательный блок `panel.rtm`).

### `circuit_calc` отсутствует для цепи

- Цепь (`circuits`) всё равно включается в `payload.circuits`.
- `payload.circuits[].calc.status = "NO_CALC"`
- Поля расчёта ΔU устанавливаются в `null`:
  - `du_v`, `du_pct`, `du_limit_pct`, `s_mm2_selected`
- `i_calc_a` берётся из входа `circuits.i_calc_a` (доступен даже без `circuit_calc`).

### `section_calc`

- `payload.bus_sections` включает **только** секции из `bus_sections` для панели.
- Для каждой секции `modes` включает только те режимы, для которых существует строка в `section_calc`
  (например, `RESERVE` может отсутствовать).

## CLI

Экспорт в файл:

```bash
python3 tools/export_payload.py --db db/project.sqlite --panel-id <PANEL_ID> --out out/payload.json
```

