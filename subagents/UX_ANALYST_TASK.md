# UX_ANALYST TASK — feature/ui-spec (MVP-UI v0.1 Streamlit Operator UI)

ROLE: UX_ANALYST  
BRANCH: `feature/ui-spec` (создать изменения и коммиты только здесь)  
SCOPE (разрешено менять): `docs/ui/*`  
SCOPE (запрещено менять): `app/*`, `db/*`, `calc_core/*`, `tools/*`, `tests/*`, `dwg/*`

## Контекст

В проекте уже есть расчётное ядро (`calc_core/*`) и CLI (`tools/*`) для:
- расчёта RTM F636-92: `calc_core.run_panel_calc` / `tools/run_calc.py`
- расчёта ΔU: `calc_core.voltage_drop.calc_panel_du`
- агрегации по секциям шин: `calc_core.section_aggregation.calc_section_loads`
- экспорта для DWG:
  - JSON payload v0.4: `tools/export_payload.py`
  - CSV mapping v0.5: `tools/export_attributes_csv.py` + `dwg/mapping_v0_5.yaml`

Проблема: нет “операторского UI” как Excel для ввода/контроля, запуска расчётов и экспорта.

## Цель

Выдать **контракт UX** в `docs/ui/STREAMLIT_UI_SPEC.md` для Streamlit Operator UI (MVP-UI v0.1), который:
- заменяет Excel по удобству ввода/контроля;
- запускает расчёты через существующие модули (не копировать формулы в UI);
- экспортирует файлы для DWG через существующие модули;
- минимизирует риск “сломать БД” (транзакции, подтверждения, запреты на calc таблицы).

## Non-negotiable требования (обязательно отразить в SPEC)

1) Таблица нагрузок как Excel:
   - `rtm_rows` editable + `rtm_row_calc` read-only + `rtm_panel_calc` summary.
2) Быстрый “мастер”: Создать панель → Заполнить RTM → Посчитать → Экспорт CSV → Импорт в DWG.
3) Видимые статусы актуальности:
   - если исходные данные изменились после `updated_at` расчёта → показывать “устарело” и кнопку пересчитать.
   - Не допускать “магии”: если без DB метаданных точно не определить — SPEC должен предложить **минимальное** и **безопасное** решение (например, UI‑мета таблица/триггеры) и явно описать fallback.
4) Запрет редактирования любых `*_calc` таблиц из UI.

## Что нужно сделать

1) Прочитать:
   - `db/schema.sql`
   - `tools/run_calc.py`, `tools/export_payload.py`, `tools/export_attributes_csv.py`
   - `calc_core/export_payload.py` (требования к наличию calc данных)
2) Обновить `docs/ui/STREAMLIT_UI_SPEC.md` так, чтобы он:
   - был “как Excel”, но безопасный;
   - имел чёткие страницы/таблицы/валидации;
   - описал реалистичный механизм **stale/актуальности** (см. non-negotiable #3).

## Acceptance criteria

- `docs/ui/STREAMLIT_UI_SPEC.md` однозначно задаёт UX/поля/валидации/статусы.
- В SPEC есть формальный алгоритм определения “устарело” (или минимальный DB‑мета контракт), без копирования формул расчёта в UI.
- SPEC явно запрещает редактирование `*_calc` и описывает защитные меры.

## Git workflow

1) `git checkout -b feature/ui-spec` (или `git checkout feature/ui-spec`)
2) Правки только в `docs/ui/*`
3) `git add docs/ui`
4) `git commit -m "docs(ui): define Streamlit Operator UI spec (MVP-UI v0.1)"`

