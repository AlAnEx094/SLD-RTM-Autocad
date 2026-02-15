# CALC_ENGINEER TASK — feature/calc-core (MVP-0.3 Section aggregation by bus_section)

ROLE: CALC_ENGINEER  
BRANCH: `feature/calc-core` (создать изменения и коммиты только здесь)  
SCOPE (разрешено менять): `calc_core/*` и `tools/*`  
SCOPE (запрещено менять): `db/*`, `tests/*`, `docs/*`, `cad_adapter/*`

## Контекст

MVP-0.3 добавляет поддержку потребителей 1 категории с двумя вводами
`NORMAL`/`RESERVE` на разные секции шин.

Нужно научиться агрегировать нагрузку по `bus_sections` для заданного режима питания.
Пока считаем только `mode='NORMAL'`, но API закладываем под `RESERVE`.

Принципы:
- Не трогать расчёт RTM и ΔU: это отдельные подсистемы.
- Не “самообманываться” через `circuits.bus_section_id` (его не вводим): источником связи являются `consumers` + `consumer_feeds`.
- DB=истина: CalcCore только читает ввод и пишет результаты.

## Цель

1) Добавить `calc_core/section_aggregation.py`:
   - `calc_section_loads(conn, panel_id: str, mode: str = 'NORMAL') -> int`
   - читает `bus_sections`, `consumers`, `consumer_feeds` для `panel_id`
   - агрегирует нагрузки по секциям шин для заданного `mode`:
     - `mode='NORMAL'`: учитывать только `consumer_feeds.feed_role='NORMAL'`
     - `mode='RESERVE'`: учитывать только `feed_role='RESERVE'` (код готовим, тестируем позже)
   - пишет результаты в `section_calc` (upsert по `(panel_id, bus_section_id, mode)`) и/или возвращает структуру для печати в CLI

2) Нагрузку потребителя брать так (MVP):
   - `load_ref_type='MANUAL'`: читать `consumers.p_kw/q_kvar/s_kva/i_a`
   - `load_ref_type='RTM_PANEL'`: читать из `rtm_panel_calc` по `load_ref_id` (или по panel_id — только если это прямо так заведено в тестах/данных)
   - `RTM_ROW` пока не обязателен

3) Добавить `section_calc` запись (предпочтительно):
   - таблица результатов (в DB):  
     `section_calc(panel_id, bus_section_id, mode, p_kw, q_kvar, s_kva, i_a, updated_at)`
   - upsert по `(panel_id, bus_section_id, mode)`

4) Обновить `tools/run_calc.py`:
   - флаг `--calc-sections` (mode NORMAL по умолчанию, опционально `--sections-mode NORMAL|RESERVE`)
   - вывод: список секций и их I/P/S

## Acceptance criteria

- В режиме `NORMAL` нагрузка попадает только в секции, связанные через `consumer_feeds(feed_role='NORMAL')`.
- В `RESERVE` (если включать) аналогично по `feed_role='RESERVE'` (без тестов на MVP-0.3).
- Backward-compat: существующие расчёты RTM и ΔU продолжают работать.

## Git workflow

1) `git checkout -b feature/calc-core` (или `git checkout feature/calc-core`)
2) Правки только в `calc_core/*` и `tools/*`
3) `git add calc_core tools`
4) `git commit -m "calc: add bus section aggregation (MVP-0.3)"`

