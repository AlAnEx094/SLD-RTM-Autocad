# UI_IMPLEMENTER TASK — feature/ui-app (MVP-UI v0.1 Streamlit Operator UI)

ROLE: UI_IMPLEMENTER  
BRANCH: `feature/ui-app` (создать изменения и коммиты только здесь)  
SCOPE (разрешено менять): `app/*`, `requirements.txt`, `docs/ui/STREAMLIT_UI_RUN.md`  
SCOPE (запрещено менять): `db/*`, `calc_core/*`, `tools/*`, `tests/*`, `dwg/*`

## Контекст

Нужно реализовать операторский Streamlit UI, который:
- даёт “Excel-like” ввод/контроль для `rtm_rows` и просмотр `rtm_row_calc` + `rtm_panel_calc`;
- запускает расчёты через существующие модули/CLI (без копирования формул);
- экспортирует JSON payload v0.4 и CSV mapping v0.5 через существующие модули;
- минимизирует риск повредить БД (транзакции, whitelists, подтверждения, read-only exports);
- показывает статусы актуальности расчётов (stale/ok/unknown) по контракту в SPEC.

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
  - “RTM Excel screen” работает (edit `rtm_rows`, view calc, summary)
  - кнопки расчёта и экспорта вызывают существующие модули
  - статусы stale отображаются согласно SPEC
  - calc таблицы только read-only

## Git workflow

1) `git checkout -b feature/ui-app` (или `git checkout feature/ui-app`)
2) Правки только в `app/*`, `requirements.txt`, `docs/ui/STREAMLIT_UI_RUN.md`
3) `git add app requirements.txt docs/ui/STREAMLIT_UI_RUN.md`
4) `git commit -m "ui: add Streamlit operator app (MVP-UI v0.1)"`

