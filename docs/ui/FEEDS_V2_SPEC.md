# FEEDS_V2_SPEC — Feeds v2 (роль ввода ≠ режим расчёта) + 2+ вводов

## 0) Цель и проблема v1

### Цель

Ввести корректную модель “Вводы / Feeds” с поддержкой 2+ (и готовностью к 3+) вводов на потребителя:

- **bus_sections = S1/S2/S3** (топология секций шин внутри щита)
- **feed_role = MAIN/RESERVE/DG/UPS/OTHER** (роль *ввода*, т.е. тип источника/ввода)
- **mode = NORMAL/EMERGENCY** (режим *расчёта*, т.е. сценарий, при котором выбирается активный ввод)

### Проблема v1 (текущее состояние до миграции)

В MVP‑0.3 (миграции `0003/0004`) используется упрощение:

- `consumer_feeds.feed_role` ∈ {`NORMAL`, `RESERVE`}
- `section_calc.mode` ∈ {`NORMAL`, `RESERVE`}

То есть **роль ввода** и **режим расчёта** были смешаны в одном понятии.

Feeds v2 вводит раздельные сущности и правила.

## 1) Glossary / Глоссарий (единые термины RU/EN)

> Дублируется в `I18N_SPEC.md`. Использовать строго эти термины.

| Concept | RU | EN |
|---|---|---|
| Panel | Щит | Panel |
| Bus section | Секция шин | Bus section |
| Consumer | Потребитель | Consumer |
| Feed | Ввод | Feed / Incoming feeder |
| Feed role | Роль ввода | Feed role |
| Calculation mode | Режим расчёта | Calculation mode |
| UI access mode | Режим доступа | Access mode |

## 2) Сущности (DB contract)

### 2.1 Справочник ролей вводов `feed_roles`

Таблица:

`feed_roles(id TEXT PK, code TEXT UNIQUE, title_ru TEXT, title_en TEXT, is_default INT)`

Seed (idempotent):

- `MAIN` (is_default=1)
- `RESERVE`
- `DG`
- `DC`
- `UPS`

Требования:

- `code` — стабильный код, используется в calc/CLI.
- `title_ru/title_en` — отображаемые названия (см. глоссарий).
- `is_default` — ровно одна роль по умолчанию (для UI/миграций).

### 2.2 Справочник режимов расчёта `modes`

Таблица:

`modes(id TEXT PK, code TEXT UNIQUE)`

Seed (idempotent):

- `NORMAL`
- `EMERGENCY`

Примечание: на первом шаге достаточно `code`; UI отображает локализованные строки через i18n.

### 2.3 Вводы потребителей `consumer_feeds` (v2)

Изменения относительно v1:

- добавить `feed_role_id` (FK → `feed_roles.id`)
- добавить `priority INT NOT NULL DEFAULT 1`
- старое поле `feed_role` (v1 enum NORMAL/RESERVE) **не использовать** в новой логике

Семантика:

- одна строка = один *ввод* потребителя (например “MAIN ввод на секцию S1”)
- `priority` используется, если для одной роли есть несколько вводов (выбор **min(priority)**)

Рекомендуемые ограничения (не обязательны, но желательны для детерминизма):

- уникальность `(consumer_id, feed_role_id, priority)` либо предотвращение дублей на уровне UI.

### 2.4 Правила выбора активной роли по режиму `consumer_mode_rules`

Таблица:

`consumer_mode_rules(consumer_id, mode_id, active_feed_role_id)`

Смысл:

- для каждого потребителя и режима фиксируем, **какая роль ввода активна** в этом режиме

Default rules (глобально ожидаемое поведение):

- `NORMAL` → `MAIN`
- `EMERGENCY` → `RESERVE`

Важно:

- если правила отсутствуют (нет записи) — calc применяет default (см. раздел 3).
- если `RESERVE` feed отсутствует — fallback логика в calc (см. раздел 3).

## 3) Контракт расчёта секций (Calc contract, v2)

### 3.1 Входы

Для каждого `panel_id` и выбранного `mode` ∈ {`NORMAL`, `EMERGENCY`}:

- `consumers` (нагрузки: либо из `rtm_panel_calc` по `load_ref_id`, либо MANUAL)
- `consumer_feeds` (вводы потребителей) с `feed_role_id` + `priority`
- `consumer_mode_rules` (выбор активной роли для режима)
- `bus_sections` (топология: S1/S2/S3)

### 3.2 Алгоритм (норматив)

Для каждого consumer:

1) Определить `active_role`:
   - взять из `consumer_mode_rules` для (consumer, mode)
   - если нет — использовать default: NORMAL→MAIN, EMERGENCY→RESERVE
2) Выбрать feed:
   - `consumer_feeds` где `feed_role_id = active_role`
   - если несколько — выбрать `min(priority)`
3) Определить `bus_section_id` из выбранного feed.
4) Определить нагрузку consumer (как в v1):
   - `RTM_PANEL`: берём P/Q/S/I из `rtm_panel_calc` по `load_ref_id`
   - `MANUAL`: берём поля `p_kw/q_kvar/s_kva/i_a` из `consumers`
5) Агрегировать в `section_calc` по `(panel_id, bus_section_id, mode)`

### 3.3 Fallbacks (обязательное поведение)

Если выбранная `active_role` не найдена среди feeds потребителя:

- попытаться fallback на `MAIN` (если режим EMERGENCY и MAIN существует), иначе на любую доступную роль по минимальному `priority`
- если feeds отсутствуют полностью — consumer пропускается с warning (как в v1)

> Конкретная стратегия fallback фиксируется в `SECTION_AGG_V2.md` (calc‑док).

### 3.4 Выходы

`section_calc` хранит итоги **по режиму расчёта**, а не по роли ввода.

Требование к значениям поля `mode` в `section_calc` после v2:

- `mode` ∈ {`NORMAL`, `EMERGENCY`}

## 4) UI contract (страницы и поведение)

UI должен обеспечить ввод/редактирование (в `EDIT`) и просмотр (в `READ_ONLY`):

### 4.1 Feed Roles

- справочник ролей вводов: просмотр всегда
- редактирование `title_ru/title_en` (опционально) — только в `EDIT`
- код `code` — read‑only

### 4.2 Consumers + Feeds

На странице управления:

- consumer: имя, `load_ref_type` (RTM_PANEL / MANUAL), `load_ref_id` (для RTM_PANEL), MANUAL поля
- feeds: N строк на consumer:
  - bus_section
  - роль ввода (из `feed_roles`)
  - priority (int)

### 4.3 Mode Rules

Для каждого consumer:

- выбрать активную роль для `NORMAL`
- выбрать активную роль для `EMERGENCY`

### 4.4 Sections / Summary

Показывать результаты `section_calc` **раздельно** для:

- `NORMAL`
- `EMERGENCY`

Все UI строки — через i18n (см. `I18N_SPEC.md`).

## 5) Backward-tolerant migration contract

Миграция должна быть tolerant к существующим БД, где присутствуют v1 данные:

### 5.1 Маппинг старых ролей feeds v1 → feed_roles v2

Если есть старые `consumer_feeds.feed_role` (v1):

- `NORMAL` → `MAIN`
- `RESERVE` → `RESERVE`

### 5.2 Старые поля после миграции

- `consumer_feeds.feed_role` (v1) считается **deprecated**:
  - может сохраняться физически для совместимости, но **не используется** в UI/calc после v2

### 5.3 Секции (section_calc)

`section_calc` после v2 считается рассчитанной сущностью; при миграции допустимо:

- либо не переносить старые значения и требовать пересчёт,
- либо выполнить best‑effort маппинг старого `RESERVE` в новый `EMERGENCY` (если реализуемо без риска).

Точный путь фиксируется DB‑инженером в миграции и тестах.

## 6) Нефункциональные требования

- Idempotent seed для справочников.
- Поддержка 3+ вводов через `priority` и отсутствие ограничений “строго два”.
- Термины в UI — едины (см. глоссарий).



## A1 update (sections by number)

- Bus sections are identified by numeric `section_no` (1..N), not by MAIN/RESERVE semantics.
- Feed role is modeled separately (`MAIN/RESERVE/DG/UPS/OTHER`) and can exist in 2+ entries.
- `mode` (`NORMAL/EMERGENCY`) drives active-role selection only; it does not redefine bus section identity.
- New explicit `bus_section_feeds` relation is used to describe section supply topology for future DWG generation.
- Legacy fields remain for backward compatibility; see `docs/contracts/FEEDS_SECTIONS_A1.md`.
