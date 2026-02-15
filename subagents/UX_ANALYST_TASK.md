# UX_ANALYST TASK — feature/ui-v0-2-spec (MVP-UI v0.2 Streamlit Operator UI)

ROLE: UX_ANALYST  
BRANCH: `feature/ui-v0-2-spec` (создать изменения и коммиты только здесь)  
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

## Цель (MVP-UI v0.2)

Обновить **контракт UX** в `docs/ui/STREAMLIT_UI_SPEC.md` для Streamlit Operator UI (MVP-UI v0.2), который делает UI реально эксплуатационным:
- **Wizard создания щита** (flow “создать → заполнить → посчитать → экспорт”)
- **Единая страница Load Table** (таблица нагрузок видна на одной странице, как Excel)
- **Жёсткая валидация ввода** (все обязательные поля, диапазоны, enum; блокировать Save/Calc/Export при ошибках)
- **Явный stale indicator** (устарело/актуально/нет расчёта/неизвестно) согласно DB контракту
- при этом сохраняет архитектурные ограничения: расчёты/экспорт только через существующие модули, никаких формул в UI, `*_calc` только read-only.

## Non-negotiable требования (обязательно отразить в SPEC)

1) Таблица нагрузок как Excel:
   - `rtm_rows` editable + `rtm_row_calc` read-only + `rtm_panel_calc` summary.
2) **Unified Load Table page**: таблица нагрузок должна быть видна и управляема **на одной странице** (layout + summary + действия).
3) **Wizard flow**: Создать панель → Заполнить RTM → Посчитать → Экспорт CSV → Импорт в DWG.
4) Видимые статусы актуальности:
   - если исходные данные изменились после `updated_at` расчёта → показывать “устарело” и кнопку пересчитать.
   - Не допускать “магии”: если без DB метаданных точно не определить — SPEC должен предложить **минимальное** и **безопасное** решение (например, UI‑мета таблица/триггеры) и явно описать fallback.
5) Запрет редактирования любых `*_calc` таблиц из UI.
6) Валидация обязательна.

## Что нужно сделать

1) Прочитать:
   - `db/schema.sql`
   - `tools/run_calc.py`, `tools/export_payload.py`, `tools/export_attributes_csv.py`
   - `calc_core/export_payload.py` (требования к наличию calc данных)
2) Обновить `docs/ui/STREAMLIT_UI_SPEC.md` так, чтобы он:
   - описал Wizard flow (шаги, UI состояния, что блокируется когда);
   - описал unified Load Table layout (где ввод, где calc, где итог, где кнопки);
   - имел чёткие правила строгой валидации по всем полям на Load Table;
   - описал реалистичный механизм **stale/актуальности** (см. non-negotiable) и как он отображается (badge/tooltip/recalc action).

## Acceptance criteria

- `docs/ui/STREAMLIT_UI_SPEC.md` однозначно задаёт UX/поля/валидации/статусы.
- В SPEC есть формальный алгоритм определения “устарело” (или минимальный DB‑мета контракт), без копирования формул расчёта в UI.
- SPEC явно запрещает редактирование `*_calc` и описывает защитные меры.

## Git workflow

1) `git checkout -b feature/ui-v0-2-spec` (или `git checkout feature/ui-v0-2-spec`)
2) Правки только в `docs/ui/*`
3) `git add docs/ui`
4) `git commit -m "docs(ui): update Streamlit Operator UI spec (MVP-UI v0.2)"`

