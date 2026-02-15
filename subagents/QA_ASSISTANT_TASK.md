# QA_ASSISTANT TASK — feature/qa-tests (MVP-0.3 Bus section aggregation)

ROLE: QA_ASSISTANT  
BRANCH: `feature/qa-tests` (создать изменения и коммиты только здесь)  
SCOPE (разрешено менять): `tests/*`  
SCOPE (запрещено менять): `db/*`, `calc_core/*`, `tools/*`, `docs/*`, `cad_adapter/*`

## Контекст

MVP-0.3 добавляет потребителя 1 категории с двумя вводами (NORMAL/RESERVE) на разные секции шин.
Нужно проверить, что расчёт агрегации по секциям в режиме `NORMAL`:
- учитывает нагрузку на NORMAL-секции
- НЕ учитывает нагрузку на RESERVE-секции

## Что нужно сделать

### 1) `tests/test_section_aggregation.py` (обязательно)

Сценарий:

- создать tmp SQLite
- применить миграции: `0001_init.sql` + `0002_circuits.sql` + `0003_bus_and_feeds.sql`
- вставить:
  - `panels` (u_ph_v обязателен только если ты используешь ток; для MANUAL можно задавать i_a явно)
  - 2 `bus_sections`: `S1`, `S2`
  - `consumer` C1:
    - `load_ref_type='MANUAL'`
    - задать `p_kw/q_kvar/s_kva/i_a` (как требует DB CHECK)
  - `consumer_feeds` для C1:
    - `NORMAL -> S1`
    - `RESERVE -> S2`
- вызвать `calc_section_loads(conn, panel_id, mode='NORMAL')`
- проверить:
  - в результатах/таблице `section_calc` нагрузка присутствует у `S1`
  - и отсутствует у `S2` (либо нулевая, но предпочтительно “нет строки”)

### 2) Smoke через CLI (опционально, но желательно)

Если `tools/run_calc.py` получит `--calc-sections`, добавь smoke:

- создать БД + данные как в тесте выше
- запустить `python tools/run_calc.py --db <tmp> --panel-id <id> --calc-sections`
- проверить, что команда завершилась успешно и результаты записаны/выведены

## Acceptance criteria

- `pytest -q` зелёный
- В `NORMAL` нагрузка сидит только на NORMAL-секции

## Git workflow

1) `git checkout -b feature/qa-tests` (или `git checkout feature/qa-tests`)
2) Правки только в `tests/*`
3) `git add tests`
4) `git commit -m "test: add section aggregation tests (MVP-0.3)"`

## Проверка

- `pytest -q`

