# UI_IMPLEMENTER TASK — i18n RU/EN + Feeds v2 pages (Streamlit UI)

ROLE: UI_IMPLEMENTER  
BRANCHES:
- `feature/i18n-ui` (сделай коммиты только про i18n здесь)
- `feature/feeds-v2-ui` (после DB+Calc merge в main, сделать UI для Feeds v2 здесь)

SCOPE (разрешено менять): `app/*`  
SCOPE (запрещено менять): `db/*`, `calc_core/*`, `tools/*`, `tests/*`, `dwg/*`

## Источник требований

- `docs/ui/I18N_SPEC.md` — i18n контракт (ключи, helper `t()`, RU default)
- `docs/ui/FEEDS_V2_SPEC.md` — термины и UI/DB/Calc контракт Feeds v2
- `docs/ui/STREAMLIT_UI_SPEC.md` — общий UX контракт (stale badges, read-only по умолчанию, и т.п.)

## Цель A — i18n (G1) в ветке `feature/i18n-ui`

### A1) Sidebar language selector (обязательно)

- Добавить selector: **Русский / English**
- RU default
- хранить выбор в `st.session_state` (например `lang`)

### A2) Вынести все пользовательские строки в JSON (обязательно)

- создать `app/i18n/ru.json` и `app/i18n/en.json`
- вынести **все** UI строки:
  - сайдбар, навигация, названия страниц
  - кнопки, подсказки, ошибки, предупреждения
  - статусы: `OK/STALE/NO_CALC/UNKNOWN`, режим доступа `READ_ONLY/EDIT`

### A3) Helper `t(key, **kwargs)` (обязательно)

- добавить helper (например `app/i18n.py` или `app/i18n/__init__.py`)
- `t(key, **kwargs)` должен:
  - выбирать словарь по `session_state["lang"]`
  - поддерживать `.format(**kwargs)`
  - fallback: если ключа нет — показывать ключ/маркер, не падать

### A4) Термины (обязательно)

Использовать единый глоссарий из SPEC (feed=ввод, mode=режим расчёта, feed_role=роль ввода, bus section=секция шин, panel=щит).

## Цель B — Feeds v2 UI (G2 UI) в ветке `feature/feeds-v2-ui`

> Важно: начинать после того, как ветки `feature/feeds-v2-db` и `feature/feeds-v2-calc` вмержены в `main`, чтобы UI опирался на новую схему/поведение.

### B1) Страницы / экраны (обязательно)

Добавить UI страницы:

- **Feed Roles** (справочник ролей)
  - просмотр всегда
  - редактирование `title_ru/title_en` (если реализуешь) — только в `EDIT`
  - `code` — read‑only

- **Consumers + Feeds**
  - consumer: имя, `load_ref_type` (RTM_PANEL/MANUAL), источник нагрузки
  - feeds: N строк на consumer:
    - bus_section
    - роль ввода (из `feed_roles`)
    - priority
  - готовность к 3+ вводам: нет UX ограничений “строго 2”

- **Mode Rules**
  - для каждого consumer выбрать:
    - активную роль для `NORMAL`
    - активную роль для `EMERGENCY`

- **Sections / Summary**
  - показывать `section_calc` **раздельно** для NORMAL и EMERGENCY

### B2) Поведение по умолчанию (обязательно)

- если для consumer отсутствуют записи `consumer_mode_rules`, UI должен:
  - предложить/создать default (NORMAL→MAIN, EMERGENCY→RESERVE) в `EDIT` (best-effort)
- отображаемые подписи роли ввода брать из `feed_roles.title_ru/title_en`

### B3) Локализация (обязательно)

Все новые страницы и поля — через i18n (`t()`), включая:

- кнопки add/edit/delete
- сообщения валидации
- подсказки по priority / fallback

## Acceptance criteria

- `pytest -q` остаётся зелёным (без правок тестов).
- RU/EN переключение работает; RU default.
- В коде UI нет жёстко прошитых пользовательских строк.
- Страницы Feeds v2 присутствуют и работают в READ_ONLY/EDIT режимах.

## Git workflow (обязательно)

### Для i18n

1) `git checkout -b feature/i18n-ui` (или `git checkout feature/i18n-ui`)
2) Правки только в `app/*`
3) `git add app`
4) `git commit -m "ui: add RU/EN i18n"`

### Для Feeds v2 UI

1) после merge DB+Calc в main: `git checkout main && git pull`
2) `git checkout -b feature/feeds-v2-ui` (или `git checkout feature/feeds-v2-ui`)
3) Правки только в `app/*`
4) `git add app`
5) `git commit -m "ui: add feeds v2 pages"`
