# CALC_ENGINEER TASK — Feeds v2 section aggregation (mode NORMAL/EMERGENCY)

ROLE: CALC_ENGINEER  
BRANCH: `feature/feeds-v2-calc` (создавай изменения и коммиты только здесь)  
SCOPE (разрешено менять): `calc_core/*`, `tools/*`, `docs/contracts/SECTION_AGG_V2.md`  
SCOPE (запрещено менять): `db/*`, `tests/*`, `app/*`, `dwg/*`

## Контекст

Feeds v2 исправляет модель:

- `feed_role` = роль ввода (MAIN/RESERVE/DG/DC/UPS)
- `mode` = режим расчёта (NORMAL/EMERGENCY)

DB изменения приходят из ветки `feature/feeds-v2-db` и включают:

- `feed_roles`, `modes`
- `consumer_feeds.feed_role_id`, `consumer_feeds.priority`
- `consumer_mode_rules(consumer_id, mode_id, active_feed_role_id)`
- `section_calc.mode` ∈ {NORMAL, EMERGENCY}

Источник требований:

- `docs/ui/FEEDS_V2_SPEC.md` — норматив по сущностям/алгоритму

## Цель

### 1) Обновить `calc_core/section_aggregation.py` (обязательно)

Требование: пересчитать секции по **активному вводу** в зависимости от `mode`.

Алгоритм (норматив, см. SPEC):

Для каждого consumer:

1) определить `active_role` для (consumer, mode):
   - из `consumer_mode_rules`
   - если нет — default: NORMAL→MAIN, EMERGENCY→RESERVE
2) выбрать feed из `consumer_feeds` с `feed_role_id=active_role`:
   - если несколько — выбрать `min(priority)`
3) определить `bus_section_id` выбранного feed
4) получить нагрузку consumer:
   - `RTM_PANEL` → из `rtm_panel_calc` по `load_ref_id`
   - `MANUAL` → из `consumers` (p/q/s/i)
5) агрегировать в `section_calc` по `(panel_id, bus_section_id, mode)`

Fallbacks (обязательное поведение):

- если нет feeds для выбранной `active_role`:
  - сделать разумный fallback (описать и зафиксировать в `SECTION_AGG_V2.md`)
  - если feeds отсутствуют — consumer пропустить с warning

Важно:

- поддержка 2+ и 3+ вводов через `priority`
- детерминизм выбора (min priority)

### 2) Обновить CLI `tools/run_calc.py` (обязательно)

- `--calc-sections --sections-mode NORMAL|EMERGENCY`
- оставить DEPRECATED alias `--mode` (как сейчас), но принимать значения NORMAL|EMERGENCY
- help‑текст обновить: это **режим расчёта секций**, не “роль ввода”

### 3) Документировать контракт расчёта (обязательно)

Создать/обновить `docs/contracts/SECTION_AGG_V2.md`:

- входные таблицы
- правила выбора активного ввода
- fallback логика
- формат результата в `section_calc` (mode = NORMAL/EMERGENCY)

## Acceptance criteria

- `calc_core.section_aggregation` корректно пишет/возвращает агрегаты для mode NORMAL и EMERGENCY.
- `tools/run_calc.py` принимает `--sections-mode NORMAL|EMERGENCY` и имеет deprecated alias `--mode`.
- Поведение задокументировано в `docs/contracts/SECTION_AGG_V2.md`.

## Git workflow (обязательно)

1) `git checkout -b feature/feeds-v2-calc` (или `git checkout feature/feeds-v2-calc`)
2) Правки только в `calc_core/*`, `tools/*`, `docs/contracts/SECTION_AGG_V2.md`
3) `git add calc_core tools docs/contracts/SECTION_AGG_V2.md`
4) `git commit -m "calc: implement feeds v2 section aggregation"`

