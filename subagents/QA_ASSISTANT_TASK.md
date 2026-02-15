# QA_ASSISTANT TASK — feature/ui-v0-2-qa (MVP-UI v0.2 Streamlit Operator UI)

ROLE: QA_ASSISTANT  
BRANCH: `feature/ui-v0-2-qa` (создать изменения и коммиты только здесь)  
SCOPE (разрешено менять): `tests/*`, `docs/ui/STREAMLIT_UI_RUN.md`  
SCOPE (запрещено менять): `db/*`, `calc_core/*`, `tools/*`, `app/*`, `dwg/*`

## Контекст

Проект добавляет операторский **Streamlit UI** (замена Excel) для ввода/контроля данных в SQLite,
запуска расчётов и экспорта JSON/CSV для DWG.

Требования:
- `pytest -q` остаётся зелёным.
- UI запускается вручную (`streamlit run app/streamlit_app.py`).
- UI **не должен** редактировать `*_calc` таблицы (только read-only).
 - Валидация в Load Table обязана блокировать некорректный ввод и действия (Save/Calc/Export).

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

### 3) Sanity: “валидация блокирует некорректный ввод” (обязательно)

Добавить тест `tests/test_streamlit_ui_validation.py`, который **без запуска webserver** проверяет:
- что функция(и) валидации Load Table (если вынесены в `app/` как pure функции) возвращают ошибки на некорректные данные.

Если валидация сейчас реализована только внутри view и её нельзя импортировать без Streamlit контекста — зафиксировать TODO:
- вынести валидацию в модуль `app/validation.py` (pure functions) и покрыть тестом.
(Тест в этом случае можно ограничить smoke-assert, что TODO записан в runbook.)

### 4) Обновить `docs/ui/STREAMLIT_UI_RUN.md`

Добавить раздел “QA smoke checklist”:
- как быстро проверить ручной запуск UI,
- какие минимальные клики сделать (выбор БД → выбрать panel → RTM table → calc → export),
- как убедиться, что calc таблицы read-only.

## Acceptance criteria

- `pytest -q` зелёный.
- Есть тест, который гарантирует, что UI код компилируется.
- В `docs/ui/STREAMLIT_UI_RUN.md` есть короткий чеклист sanity.

## Git workflow

1) `git checkout -b feature/ui-v0-2-qa` (или `git checkout feature/ui-v0-2-qa`)
2) Правки только в `tests/*` и (опционально) `docs/ui/STREAMLIT_UI_RUN.md`
3) `git add tests docs/ui/STREAMLIT_UI_RUN.md`
4) `git commit -m "test: add UI v0.2 validation and smoke checks"`

