# QA_ASSISTANT TASK — feature/qa-tests (MVP-0.5 DWG mapping + CSV attributes export)

ROLE: QA_ASSISTANT  
BRANCH: `feature/qa-tests` (создать изменения и коммиты только здесь)  
SCOPE (разрешено менять): `tests/*`  
SCOPE (запрещено менять): `db/*`, `calc_core/*`, `tools/*`, `docs/*`, `cad_adapter/*`

## Контекст

MVP-0.5 добавляет экспорт CSV атрибутов DWG на основе mapping YAML и payload v0.4.
Экспорт читает **только результаты** из БД и не запускает расчёты.

## Что нужно сделать

### 1) `tests/test_export_attributes_csv_smoke.py` (обязательно)

Smoke сценарий:

- создать tmp SQLite
- применить миграции `0001..0004`
- вставить минимальные данные (как в payload smoke):
  - `panels` + обязательный `rtm_panel_calc`
  - `bus_sections` + `section_calc` (хотя бы NORMAL)
  - `circuits` + `circuit_calc` (хотя бы для одной цепи, вторую оставить без calc для `NO_CALC`)
- создать mapping YAML (в tmp dir) или использовать `dwg/mapping_v0_5.yaml`
- вызвать CLI:
  - `python tools/export_attributes_csv.py --db <tmp> --panel-id <id> --mapping <yaml> --out-dir <dir>`
- проверить:
  - файлы созданы: `attrs_panel.csv`, `attrs_circuits.csv`, `attrs_sections.csv`
  - в файлах есть строки с ожидаемыми GUID:
    - panel_id присутствует в `attrs_panel.csv`
    - circuit_id присутствуют в `attrs_circuits.csv`
    - bus_section_id присутствует в `attrs_sections.csv`

## Acceptance criteria

- `pytest -q` зелёный
- Экспорт не зависит от запуска расчётов (только от наличия результатов в БД)

## Git workflow

1) `git checkout -b feature/qa-tests` (или `git checkout feature/qa-tests`)
2) Правки только в `tests/*`
3) `git add tests`
4) `git commit -m "test: add attributes CSV export smoke (MVP-0.5)"`

## Проверка

- `pytest -q`

