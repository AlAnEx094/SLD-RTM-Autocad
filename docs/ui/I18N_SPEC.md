# I18N_SPEC — локализация Streamlit UI (RU/EN) для SLD-RTM-AutoCAD

## 0) Цель

Ввести i18n для операторского Streamlit UI:

- **RU/EN переключение** в сайдбаре (вариант A).
- **RU по умолчанию**.
- **100% пользовательских строк** вынесены в словари `app/i18n/ru.json` и `app/i18n/en.json`.
- Вся отрисовка UI использует helper `t(key, **kwargs)`.

Документ фиксирует контракт UI/терминов, чтобы i18n не “разъехался” при развитии Feeds v2.

## 1) Glossary / Глоссарий (единые термины RU/EN)

> Использовать эти переводы в UI, документации, подсказках и в `feed_roles.title_*`.

| Concept | RU | EN | Notes |
|---|---|---|---|
| Panel (switchboard) | **Щит** | **Panel** | Сущность `panels` (ранее иногда “switchboard” — не использовать). |
| Bus section | **Секция шин** | **Bus section** | `bus_sections` (обычно S1/S2/S3). |
| Consumer | **Потребитель** | **Consumer** | `consumers`. |
| Feed | **Ввод** | **Feed / Incoming feeder** | Строка в `consumer_feeds` (конкретный ввод потребителя). |
| Feed role | **Роль ввода** | **Feed role** | `feed_roles`: MAIN/RESERVE/DG/DC/UPS. |
| Calculation mode | **Режим расчёта** | **Calculation mode** | `modes`: NORMAL/EMERGENCY. **Не путать** с режимом UI. |
| UI access mode | **Режим доступа** | **Access mode** | `READ_ONLY` / `EDIT` (UI). |
| Status | **Статус** | **Status** | `OK/STALE/NO_CALC/UNKNOWN`. |

## 2) UX requirements (Variant A)

- В сайдбаре добавить selector **“Русский / English”**.
- Значение хранить в `st.session_state["lang"]`.
- **Коды языков**: `"RU"` и `"EN"` (это значения состояния; отображаемые подписи локализуются).
- **Default = RU** (при первом запуске сессии и при отсутствии значения).
- Переключение языка **не должно** менять данные в БД; только перерисовка UI.

## 3) Файлы локализации (JSON)

Используются (обязательны в репозитории):

- `app/i18n/ru.json` (RU)
- `app/i18n/en.json` (EN)

Требования:

- JSON — UTF‑8.
- Ключи строк — **стабильные**, **dot‑namespaced** (рекомендуется) вида `namespace.sub.key`.
- Значения — **только пользовательский текст**.
- Словари должны быть **симметричными**: одинаковый набор ключей в RU и EN.
- Параметризация — только через `str.format` с **именованными** параметрами: `{path}`, `{count}`, `{mode}` и т.д.

Рекомендуемая структура ключей:

- `app.title`
- `sidebar.db_path`, `sidebar.access_mode`, `sidebar.language`, `sidebar.active_panel`, `sidebar.navigation`
- `nav.db_connect`, `nav.overview`, `nav.wizard`, `nav.panels`, `nav.rtm`, `nav.calculate`, `nav.export`
- `access_mode.read_only`, `access_mode.edit`, `access_mode.confirm_edit`
- `status.ok`, `status.stale`, `status.no_calc`, `status.unknown`, `status.hidden`
- `buttons.save`, `buttons.recalculate`, `buttons.export`, `buttons.delete`, …
- `validation.*`, `errors.*`, `tooltips.*`
- `feeds.*`, `consumers.*`, `bus_sections.*`, `mode_rules.*`, `feed_roles.*`

## 4) Helper `t(key, **kwargs)` — контракт

Расположение (норма проекта):

- реализация: `app/i18n/core.py`
- публичный импорт: `from app.i18n import t` (реэкспорт из `app/i18n/__init__.py`)

UI использует единый helper:

- `t(key: str, **kwargs) -> str`
- выбирает словарь по `session_state["lang"]` (RU/EN).
- поддерживает параметризацию через `.format(**kwargs)`:
  - пример: `t("errors.db_not_found", path=db_path)`
- fallback поведение:
  - если ключ отсутствует — вернуть сам ключ (или `??{key}??`), чтобы пропуски были видны.
  - не падать исключением на отсутствующих ключах в production UI.

Опционально (желательно для качества):

- В dev режиме собирать missing keys в список и показывать в debug‑панели.

## 5) Обязательные строки (минимальный набор ключей)

Этот список — **минимум**, который должен существовать в обоих словарях. Фактический “полный” список = все ключи, используемые в коде через `t("...")` (проверяется тестом).

### 5.1) App + Sidebar

- `app.title`
- `sidebar.db_path`
- `sidebar.access_mode`
- `sidebar.language`
- `sidebar.lang_ru`
- `sidebar.lang_en`
- `sidebar.active_panel`
- `sidebar.navigation`
- `sidebar.none`

### 5.2) Навигация (страницы)

- `nav.db_connect`
- `nav.overview`
- `nav.wizard`
- `nav.panels`
- `nav.rtm`
- `nav.calculate`
- `nav.feed_roles`
- `nav.consumers_feeds`
- `nav.mode_rules`
- `nav.sections_summary`
- `nav.export`

### 5.3) Режим доступа UI

- `access_mode.read_only`
- `access_mode.edit`
- `access_mode.confirm_edit`

### 5.4) Статусы актуальности

- `status.ok`
- `status.stale`
- `status.no_calc`
- `status.unknown`

### 5.5) Режимы расчёта (Feeds v2)

- `mode.normal`
- `mode.emergency`

## 5) Что считается “пользовательской строкой”

Подлежит локализации **всё**, что видит пользователь:

- заголовки страниц, названия вкладок/страниц, навигация
- лейблы форм/таблиц, подсказки, help‑тексты
- текст кнопок
- предупреждения/ошибки/инфо‑сообщения (`st.error/warning/info/success`)
- статусы (`OK/STALE/NO_CALC/UNKNOWN`, `READ_ONLY/EDIT`)
- тексты подтверждений (например “I understand this will modify DB”)
- placeholder‑тексты и “(none)”

Не локализуются (как правило):

- коды/enum, которые являются **данными/контрактом** (например `feed_roles.code`, `modes.code`), но их отображаемые подписи **локализуются**.

## 6) Отображение справочников (Feeds v2)

Для Feeds v2 UI должен:

- показывать **роль ввода** по `feed_roles.title_ru/title_en` (а не по `code`)
- показывать **режим расчёта** по `modes.code` через локализованную строку UI (или через справочник, если добавим `title_*` в будущем)

Ключевые тексты (обязательные):

- “Режим расчёта: Нормальный / Аварийный” (`NORMAL/EMERGENCY`)
- “Роль ввода: Основной / Резервный / ДГУ / DC / UPS” (`MAIN/RESERVE/DG/DC/UPS`)

## 7) Acceptance criteria (Definition of Done)

- Переключатель языка присутствует в сайдбаре, RU default.
- В коде UI **нет** “жёстко прошитых” пользовательских строк (кроме ключей/кодовых enum и тех, что приходят из БД).
- Статусы и режимы доступа отображаются локализовано.
- `ru.json` и `en.json` содержат полный набор используемых ключей.

