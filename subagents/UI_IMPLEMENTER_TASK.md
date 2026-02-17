# UI_IMPLEMENTER TASK — MVP-BAL v0.3a (bind circuits to bus sections in UI)

ROLE: UI_IMPLEMENTER  
BRANCH: `feature/circuits-section-ui` (создавай изменения и коммиты только здесь)  

SCOPE (разрешено менять): `app/*`  
SCOPE (запрещено менять): `db/*`, `calc_core/*`, `tools/*`, `tests/*`, `dwg/*`, `docs/*`

## Источник требований

- `docs/contracts/PHASE_BALANCE_V0_1.md`
- `docs/contracts/PHASE_BALANCE_V0_3A.md` (v0.3a)
- `docs/ui/I18N_SPEC.md` (non-negotiable: все строки через `t()`, RU/EN)

## Предпосылки (в main после DB+Calc merge)

В БД присутствуют:

- `circuits.phase` (`L1/L2/L3`)
- `circuits.bus_section_id` (nullable FK -> bus_sections.id)
- `panel_phase_balance(panel_id, mode, i_l1, i_l2, i_l3, unbalance_pct, updated_at, invalid_manual_count, warnings_json)`

В `calc_core` присутствует:

- `calc_core.phase_balance.balance_panel(...)` (или эквивалентный API) и CLI флаг в `tools/run_calc.py`

## Цель (обязательно)

### 1) pb-mode selector + запуск балансировки (обязательно)

Добавить UI действие (рекомендуемое место: `app/views/calculate.py`, рядом с RTM/DU/SECTIONS):

- кнопка **“Балансировка фаз”**
- доступна только в `EDIT` (как и другие расчёты)
- вызывает фазную балансировку (через `calc_core.phase_balance` или через CLI-обёртку) и обновляет состояние (rerun)
- добавить чекбокс (default ON):
  - RU: “Не изменять вручную назначенные фазы”
  - EN: “Do not overwrite manually assigned phases”
  - передавать `respect_manual` в вызов расчёта
- добавить selector `pb-mode` = `NORMAL|EMERGENCY` (RU/EN через i18n)
- использовать выбранный mode для:
  - чтения `panel_phase_balance` (display)
  - запуска `calc_phase_balance(..., mode=selected_mode, ...)` (storage)

### 1.1) Warning banner + details (обязательно)

- если `panel_phase_balance.invalid_manual_count > 0`:
  - показать persistent warning banner (i18n RU/EN)
  - показать expandable список/таблицу offending circuits из `warnings_json`
- hide/auto-clear UX:
  - если `invalid_manual_count == 0` → banner/expander не должны отображаться
  - если `warnings_json` пустой/NULL → expander не показывать

#### v0.3a EMERGENCY warnings (обязательно)

- если выбран `pb-mode=EMERGENCY` и среди 1Φ цепей есть `bus_section_id IS NULL`:
  - показать warning banner (RU/EN через i18n)
- если calc записал в `warnings_json` предупреждение с причиной `EMERGENCY_SECTIONS_NOT_COMPUTED`:
  - показать warning banner, что аварийные секции не рассчитаны и применён fallback

### 2) Таблица цепей с фазой

Отображение:

- таблица `circuits` для выбранного щита
- колонка `phase`:
  - для 1Ф цепей (`phases=1`) показывать `L1/L2/L3` (или пусто, если NULL)
  - для 3Ф цепей (`phases=3`) показывать `—`/пусто и сделать read-only

Редактирование (только `EDIT`):

- дать возможность вручную менять `circuits.phase` для 1Ф цепей
- валидировать допустимые значения: `L1|L2|L3|empty`
- запись только в БД (DB = truth)
- при ручном редактировании фазы выставлять `circuits.phase_source='MANUAL'`
- показывать колонку `phase_source` в таблице (AUTO/MANUAL) с локализованными лейблами
- добавить индикатор колонку (например `Status` или `⚠`) для цепей, где:
  - `phase_source='MANUAL'` и `phase` пустой/невалидный
  - индикатор и подписи — через i18n (`t(...)`), без хардкода

#### v0.3a: привязка цепи к секции шин (обязательно)

- добавить колонку `bus_section` (или `bus_section_id`) в таблицу 1Φ цепей
- в `EDIT` сделать dropdown по доступным `bus_sections` текущего щита:
  - option “—”/empty = `NULL`
  - остальные options = имена секций (value сохранять как `bus_section_id`)
- сохранять изменения только в БД (DB = truth)

### 3) Итоги баланса по фазам + неравномерность

Показывать:

- `I(L1)`, `I(L2)`, `I(L3)` (А)
- `unbalance_pct` (%)
- `updated_at`

Источник истины:

- читать из `panel_phase_balance` (по `mode=NORMAL` в v0.1, если UI не даёт выбора mode)

### 4) i18n compliance (non-negotiable)

Все новые строки UI и подписи:

- добавить ключи в `app/i18n/ru.json` и `app/i18n/en.json`
- использовать `t("...")` в UI
- не добавлять хардкод строк

## Acceptance criteria

- Кнопка “Балансировка фаз” видна и работает (обновляет `circuits.phase` и `panel_phase_balance`).
- Таблица цепей показывает/даёт редактировать фазу (в `EDIT`).
- Итоги по фазам + `unbalance_pct` отображаются из БД.
- `pytest -q` остаётся зелёным.

## Git workflow (обязательно)

1) `git checkout -b feature/circuits-section-ui` (или `git checkout feature/circuits-section-ui`)
2) Правки только в `app/*`
3) `git add app`
4) `git commit -m "ui: bind circuits to bus sections"`
