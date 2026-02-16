# UI_IMPLEMENTER TASK — Phase Balance v0.1 (Streamlit UI + i18n)

ROLE: UI_IMPLEMENTER  
BRANCH: `feature/phase-balance-ui` (создавай изменения и коммиты только здесь)  

SCOPE (разрешено менять): `app/*`  
SCOPE (запрещено менять): `db/*`, `calc_core/*`, `tools/*`, `tests/*`, `dwg/*`, `docs/*`

## Источник требований

- `docs/contracts/PHASE_BALANCE_V0_1.md`
- `docs/ui/I18N_SPEC.md` (non-negotiable: все строки через `t()`, RU/EN)

## Предпосылки (в main после DB+Calc merge)

В БД присутствуют:

- `circuits.phase` (`L1/L2/L3`)
- `panel_phase_balance(panel_id, mode, i_l1, i_l2, i_l3, unbalance_pct, updated_at)`

В `calc_core` присутствует:

- `calc_core.phase_balance.balance_panel(...)` (или эквивалентный API) и CLI флаг в `tools/run_calc.py`

## Цель (обязательно)

### 1) Кнопка запуска “Балансировка фаз”

Добавить UI действие (рекомендуемое место: `app/views/calculate.py`, рядом с RTM/DU/SECTIONS):

- кнопка **“Балансировка фаз”**
- доступна только в `EDIT` (как и другие расчёты)
- вызывает фазную балансировку (через `calc_core.phase_balance` или через CLI-обёртку) и обновляет состояние (rerun)

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

1) `git checkout -b feature/phase-balance-ui` (или `git checkout feature/phase-balance-ui`)
2) Правки только в `app/*`
3) `git add app`
4) `git commit -m "ui: add phase balance controls"`
