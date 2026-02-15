# CALC_ENGINEER TASK — feature/calc-core (MVP-0.5 DWG mapping + CSV attributes export)

ROLE: CALC_ENGINEER  
BRANCH: `feature/calc-core` (создать изменения и коммиты только здесь)  
SCOPE (разрешено менять): `calc_core/*` и `tools/*`  
SCOPE (запрещено менять): `db/*`, `tests/*`, `docs/*`, `cad_adapter/*`

## Контекст

MVP-0.5 добавляет слой маппинга атрибутов DWG и экспорт CSV для заполнения атрибутов блоков
через внешний LISP/Script (без AutoCAD API).

Вход: JSON payload v0.4 (получаем через `calc_core.export_payload.build_payload`).

Цель: по YAML mapping генерировать CSV:
- `attrs_panel.csv`  (GUID,ATTR,VALUE)
- `attrs_circuits.csv` (GUID,ATTR,VALUE)
- `attrs_sections.csv` (GUID,MODE,ATTR,VALUE)

## Цель

### 1) Mapping YAML

Файл mapping (в репозитории): `dwg/mapping_v0_5.yaml`

Пример структуры:

```yaml
panel:
  block_guid_attr: "GUID"
  attributes:
    PP_KW: "panel.rtm.pp_kw"
    IP_A:  "panel.rtm.ip_a"
circuits:
  block_guid_attr: "GUID"
  attributes:
    CIR_NAME: "name"
    I_A: "calc.i_calc_a"
    DU_PCT: "calc.du_pct"
    S_MM2: "calc.s_mm2_selected"
sections:
  block_guid_attr: "GUID"
  attributes:
    PP_KW: "modes.{MODE}.pp_kw"
    IP_A:  "modes.{MODE}.ip_a"
  modes: ["NORMAL","RESERVE"]
```

### 2) CalcCore: `calc_core/export_attributes_csv.py`

Добавить модуль:
- `load_mapping(path: str | Path) -> dict` (читает YAML)
- `build_rows_from_payload(payload: dict, mapping: dict) -> dict[str, list[list[str]]]`
  - возвращает 3 набора строк: `panel`, `circuits`, `sections`
  - строки уже с форматированным VALUE

Решение по отсутствующим полям:
- Если json_path ведёт в отсутствующее поле или значение `None` → **VALUE = ''** (пустая строка), строку **не пропускать**.

Форматирование чисел (дефолт, без опций в mapping):
- `*_kw`, `*_kvar`, `*_kva`, `pp_kw/qp_kvar/sp_kva/p_kw/q_kvar/s_kva` → 2 знака
- `*_a`, `ip_a`, `i_a`, `i_calc_a` → 1 знак
- `du_pct`, `du_limit_pct` → 2 знака
- `length_m` → 0 знаков
- иначе: если число → без лишних хвостов (или 2 знака по умолчанию, но зафиксировать поведение в docs)

### 3) Tools: `tools/export_attributes_csv.py`

CLI, который **не запускает расчёты**:
- args: `--db`, `--panel-id`, `--mapping dwg/mapping_v0_5.yaml`, `--out-dir out/`
- читает payload через `build_payload(conn, panel_id)`
- пишет 3 CSV файла в UTF-8:
  - `attrs_panel.csv` header: `GUID,ATTR,VALUE`
  - `attrs_circuits.csv` header: `GUID,ATTR,VALUE`
  - `attrs_sections.csv` header: `GUID,MODE,ATTR,VALUE`

### 4) Docs

Добавить `docs/contracts/DWG_MAPPING_V0_5.md`:
- что такое GUID и как LISP/Script матчится по GUID
- формат CSV файлов
- как задавать mapping YAML (панель/цепи/секции)
- правила отсутствующих полей и `NO_CALC`

## Acceptance criteria

- `tools/export_attributes_csv.py` не пишет в БД и не запускает расчёты.
- CSV файлы создаются и имеют ожидаемые заголовки/строки.
- Существующие CLI не ломаются.

## Git workflow

1) `git checkout -b feature/calc-core` (или `git checkout feature/calc-core`)
2) Правки только в `calc_core/*` и `tools/*`
3) `git add calc_core tools`
4) `git commit -m "calc: add DWG mapping and CSV attributes export (MVP-0.5)"`

