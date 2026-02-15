# UI_IMPLEMENTER TASK — feature/ui-v0-2-impl (MVP-UI v0.2 Streamlit Operator UI)

ROLE: UI_IMPLEMENTER  
BRANCH: `feature/ui-v0-2-impl` (создать изменения и коммиты только здесь)  
SCOPE (разрешено менять): `app/*`, `requirements.txt`, `docs/ui/STREAMLIT_UI_RUN.md`  
SCOPE (запрещено менять): `db/*`, `calc_core/*`, `tools/*`, `tests/*`, `dwg/*`

## Контекст

Обновить Streamlit UI до MVP-UI v0.2, чтобы он был реально удобен в эксплуатации:
- добавить Wizard создания щита (end-to-end flow);
- реализовать **unified Load Table** страницу (ввод + calc + итоги + кнопки действий на одной странице);
- усилить валидацию (строгие правила; блокировать Save/Calc/Export при ошибках);
- сделать явные stale badges по контракту SPEC;
- при этом **не ломать** существующий функционал (Calculate/Export/DB Connect) и архитектурные ограничения.

## Источник требований

1) `docs/ui/STREAMLIT_UI_SPEC.md` — главный UX контракт.
2) `db/schema.sql` + `db/migrations/*.sql` — фактические таблицы.
3) `tools/run_calc.py` / `calc_core.run_panel_calc` / `calc_core.voltage_drop.calc_panel_du` / `calc_core.section_aggregation.calc_section_loads`
4) Экспорт:
   - `tools/export_payload.py` / `calc_core.export_payload.build_payload`
   - `tools/export_attributes_csv.py` / `calc_core.export_attributes_csv.*`

## Жёсткие ограничения

- Нельзя редактировать любые `*_calc` таблицы из UI.
- Нельзя дублировать расчётные формулы в UI; расчёты запускать через существующие функции/модули.
- Все SQL параметризованные; никакого конкатенирования пользовательского ввода.
- UI должен работать с SQLite файлом, выбранным пользователем (default `db/project.sqlite`).

## Deliverables

- `app/streamlit_app.py` — точка входа
- `app/db.py` — безопасный SQLite слой: connect/tx/schema checks/CRUD с whitelist
- `app/views/*.py` — страницы по SPEC
- `docs/ui/STREAMLIT_UI_RUN.md` — запуск + быстрый сценарий + примечания
- `requirements.txt` — добавить `streamlit` (и минимум нужных зависимостей, например `pandas`)

## Acceptance criteria

- `pytest -q` остаётся зелёным.
- `streamlit run app/streamlit_app.py` запускается вручную.
- В UI:
  - Wizard работает: создать панель → Load Table → calc → export
  - unified Load Table: edit `rtm_rows`, read-only `rtm_row_calc`, read-only `rtm_panel_calc` на одной странице
  - строгая валидация блокирует некорректный ввод и опасные действия
  - stale badges отображаются согласно SPEC
  - calc таблицы только read-only

## Git workflow

1) `git checkout -b feature/ui-v0-2-impl` (или `git checkout feature/ui-v0-2-impl`)
2) Правки только в `app/*`, `requirements.txt`, `docs/ui/STREAMLIT_UI_RUN.md`
3) `git add app requirements.txt docs/ui/STREAMLIT_UI_RUN.md`
4) `git commit -m "ui: improve operator UX (MVP-UI v0.2)"`

