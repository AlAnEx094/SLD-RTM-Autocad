# QA_ASSISTANT TASK — feature/ui-qa (MVP-UI v0.1 Streamlit Operator UI)

ROLE: QA_ASSISTANT  
BRANCH: `feature/ui-qa` (создать изменения и коммиты только здесь)  
SCOPE (разрешено менять): `tests/*`, `docs/ui/STREAMLIT_UI_RUN.md`  
SCOPE (запрещено менять): `db/*`, `calc_core/*`, `tools/*`, `app/*`, `dwg/*`

## Контекст

Проект добавляет операторский **Streamlit UI** (замена Excel) для ввода/контроля данных в SQLite,
запуска расчётов и экспорта JSON/CSV для DWG.

Требования:
- `pytest -q` остаётся зелёным (сейчас 14 passed).
- UI запускается вручную (`streamlit run app/streamlit_app.py`).
- UI **не должен** редактировать `*_calc` таблицы (только read-only).

## Что нужно сделать (минимум, high-signal)

### 1) Smoke тест на “код UI компилируется” (обязательно)

Добавить тест `tests/test_streamlit_ui_smoke.py`, который:
- не поднимает веб-сервер,
- не требует реальной БД,
- проверяет, что модуль(и) `app/*` компилируются:
  - через `python -m compileall app`
  - (или через `compileall.compile_dir("app", quiet=1)`)

Цель: ловить синтаксические ошибки/опечатки в UI коде при CI запуске `pytest`.

### 2) Sanity: “UI не пишет в calc таблицы” (best-effort, без вторжения в app)

Если возможно без сложного рефакторинга UI, добавь **узкий** тест, который:
- создаёт tmp SQLite,
- прогоняет `tools/run_calc.ensure_migrations(tmp_db)` (чтобы схема была реальная),
- импортирует только слой DB-хелперов UI (например `app/db.py`) и проверяет whitelist таблиц:
  - список разрешённых для записи таблиц **НЕ содержит** `rtm_row_calc`, `rtm_panel_calc`, `circuit_calc`, `section_calc`, `panel_phase_calc`

Если такой whitelist не реализован в UI (или импорт тяжёлый) — пропусти пункт и зафиксируй это как TODO в `docs/ui/STREAMLIT_UI_RUN.md`.

### 3) Обновить `docs/ui/STREAMLIT_UI_RUN.md` (после появления файла)

Добавить раздел “QA smoke checklist”:
- как быстро проверить ручной запуск UI,
- какие минимальные клики сделать (выбор БД → выбрать panel → RTM table → calc → export),
- как убедиться, что calc таблицы read-only.

## Acceptance criteria

- `pytest -q` зелёный.
- Есть тест, который гарантирует, что UI код компилируется.
- В `docs/ui/STREAMLIT_UI_RUN.md` есть короткий чеклист sanity.

## Git workflow

1) `git checkout -b feature/ui-qa` (или `git checkout feature/ui-qa`)
2) Правки только в `tests/*` и (опционально) `docs/ui/STREAMLIT_UI_RUN.md`
3) `git add tests docs/ui/STREAMLIT_UI_RUN.md`
4) `git commit -m "test: add Streamlit UI smoke and sanity checklist (MVP-UI v0.1)"`

