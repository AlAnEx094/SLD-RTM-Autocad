# QA_ASSISTANT TASK — feature/qa-tests (MVP-0.4 Export DWG JSON payload)

ROLE: QA_ASSISTANT  
BRANCH: `feature/qa-tests` (создать изменения и коммиты только здесь)  
SCOPE (разрешено менять): `tests/*`  
SCOPE (запрещено менять): `db/*`, `calc_core/*`, `tools/*`, `docs/*`, `cad_adapter/*`

## Контекст

MVP-0.4 добавляет экспорт JSON payload (для будущей синхронизации с DWG).
Экспорт читает **только результаты** из БД и не запускает расчёты.

## Что нужно сделать

### 1) `tests/test_export_payload_smoke.py` (обязательно)

Smoke сценарий (shape-only):

- создать tmp SQLite
- применить миграции `0001..0004`
- вставить минимальные данные:
  - `panels` + обязательный `rtm_panel_calc` для `panel_id` (иначе export должен падать)
  - несколько `bus_sections` + `section_calc` (хотя бы NORMAL для одной секции)
  - несколько `circuits`
  - `circuit_calc` только для части circuits, чтобы проверить `NO_CALC`
- вызвать `calc_core.export_payload.build_payload(conn, panel_id)`
- проверить:
  - `payload['version'] == '0.4'`
  - ключи `panel/bus_sections/circuits/dwg_contract` присутствуют
  - длины массивов соответствуют вставленным сущностям
  - для цепи без `circuit_calc`: `calc.status == 'NO_CALC'` и поля расчёта `None`

### 2) Smoke через CLI `tools/export_payload.py` (желательно)

- создать БД + данные как в тесте выше
- запустить `python tools/export_payload.py --db <tmp> --panel-id <id> --out <tmp.json>`
- проверить:
  - файл создан
  - JSON парсится
  - `version == '0.4'`

## Acceptance criteria

- `pytest -q` зелёный
- Экспорт не зависит от запуска расчётов (только от наличия результатов в БД)

## Git workflow

1) `git checkout -b feature/qa-tests` (или `git checkout feature/qa-tests`)
2) Правки только в `tests/*`
3) `git add tests`
4) `git commit -m "test: add payload export smoke (MVP-0.4)"`

## Проверка

- `pytest -q`

