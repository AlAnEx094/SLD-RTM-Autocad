# CAD_INTEGRATOR TASK — feature/cad-adapter

ROLE: CAD_INTEGRATOR  
BRANCH: `feature/cad-adapter` (создать изменения и коммиты только здесь)  
SCOPE (разрешено менять): `cad_adapter/*`  
SCOPE (запрещено менять): `db/*`, `calc_core/*`, `tools/*`, `tests/*`, `docs/*`

## Контекст

На MVP-0.1 AutoCAD API не используется. `cad_adapter` должен оставаться **read-only** к SQLite:
DB → DWG payload (пока просто печать JSON).

В актуальной схеме результаты щита лежат в:
- `rtm_panel_calc` (итоги РТМ по щиту)
- `panel_phase_calc` (итоги фазировки, может быть пусто если фазировка не реализована)

## Цель

Оставить scaffold без AutoCAD API, но довести до “чистого” контракта:

### `sync_from_db(db_path: str, panel_id: str) -> None`

- только read-only подключение к SQLite
- читает `rtm_panel_calc` и `panel_phase_calc` по `panel_id`
- печатает JSON payload
- **не модифицирует** БД

## Что нужно сделать

- Проверить, что `cad_adapter/dwg_sync.py`:
  - использует `mode=ro` (URI)
  - корректно обрабатывает отсутствие строк (payload с `null`, но понятная ошибка/exit code в CLI)
  - не импортирует `calc_core` и не зависит от расчёта
- При необходимости — почистить CLI/ошибки/сообщения (без изменения внешнего контракта payload)

## Git workflow

1) `git checkout feature/cad-adapter`
2) Правки только в `cad_adapter/*`
3) `git add cad_adapter`
4) `git commit -m "cad: harden DWG sync scaffold (read-only)"`

## Проверка

- Можешь локально проверить командой:
  - `python3 cad_adapter/dwg_sync.py --db db/project.sqlite --panel-id <GUID>`
  - (если БД/панели нет — ожидаем аккуратную ошибку)

