# DWG_MAPPING v0.5 — контракт YAML маппинга и CSV атрибутов

Этот документ фиксирует формат YAML mapping и выходные CSV для заполнения
атрибутов блоков через внешний LISP/Script (без AutoCAD API).

## GUID и матчинг блоков

- Все идентификаторы (`panel_id`, `circuit_id`, `bus_section_id`) — GUID строкового типа.
- В DWG у блока должен быть атрибут, который хранит GUID.
- Имя этого атрибута задается в mapping как `block_guid_attr`.
- CSV использует отдельную колонку `GUID`; LISP/Script матчится по GUID и
  пишет значения в атрибуты блока.

## CSV форматы

Файлы создаются в UTF-8:

- `attrs_panel.csv` — `GUID,ATTR,VALUE`
- `attrs_circuits.csv` — `GUID,ATTR,VALUE`
- `attrs_sections.csv` — `GUID,MODE,ATTR,VALUE`

`ATTR` — имя атрибута блока (ключ из mapping).  
`VALUE` — значение атрибута, уже отформатированное.

## Mapping YAML структура

```yaml
panel:
  block_guid_attr: "GUID"
  attributes:
    PP_KW: "panel.rtm.pp_kw"
    IP_A: "panel.rtm.ip_a"
circuits:
  block_guid_attr: "GUID"
  attributes:
    CIR_NAME: "name"
    I_A: "calc.i_calc_a"
    DU_PCT: "calc.du_pct"
    S_MM2: "calc.s_mm2_selected"
sections:
  block_guid_attr: "GUID"
  attributes:
    PP_KW: "modes.{MODE}.pp_kw"
    IP_A: "modes.{MODE}.ip_a"
  modes: ["NORMAL","RESERVE"]
```

Правила разрешения путей:
- `panel` — абсолютный путь от корня payload (например `panel.rtm.pp_kw`).
- `circuits` — путь относительно объекта цепи (например `name`, `calc.du_pct`).
- `sections` — путь относительно объекта секции. Поддерживается `{MODE}`
  (например `modes.{MODE}.pp_kw`), список `modes` задается в mapping.

## Отсутствующие поля и NO_CALC

- Если путь отсутствует в payload или значение `null` → `VALUE = ''`
  (пустая строка), строка не пропускается.
- Для `circuits` со статусом `calc.status = "NO_CALC"` поля расчёта
  (`du_pct`, `du_limit_pct`, `s_mm2_selected` и т.д.) равны `null`, значит в CSV
  будет пустая строка.

## Форматирование чисел (по умолчанию)

Применяется по последнему сегменту пути:
- `*_kw`, `*_kvar`, `*_kva`, `pp_kw/qp_kvar/sp_kva/p_kw/q_kvar/s_kva` → 2 знака
- `*_a`, `ip_a`, `i_a`, `i_calc_a` → 1 знак
- `du_pct`, `du_limit_pct` → 2 знака
- `length_m` → 0 знаков
- иначе: число форматируется с максимумом 6 знаков после запятой, без хвостов
