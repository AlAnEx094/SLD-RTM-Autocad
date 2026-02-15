# CAD_INTEGRATOR TASK — feature/cad-adapter (MVP-0.6 AutoLISP CSV import by GUID)

ROLE: CAD_INTEGRATOR  
BRANCH: `feature/cad-adapter` (создать изменения и коммиты только здесь)  
SCOPE (разрешено менять): `dwg/lisp/*`, `docs/contracts/*`  
SCOPE (запрещено менять): `db/*`, `calc_core/*`, `tools/*`, `tests/*`, `cad_adapter/*`

## Контекст

MVP-0.6 добавляет **AutoLISP** скрипт для импорта CSV атрибутов в DWG по GUID.
AutoCAD API/.NET не используем — только LISP.

CSV генерируются внешней утилитой (MVP-0.5):
- `attrs_panel.csv` (GUID,ATTR,VALUE)
- `attrs_circuits.csv` (GUID,ATTR,VALUE)
- `attrs_sections.csv` (GUID,MODE,ATTR,VALUE)

## Цель

Сделать универсальную команду AutoLISP `IMPORT_ATTRS`, которая:
- читает CSV из папки пользователя
- находит block references (`INSERT`) с атрибутом `GUID`
- обновляет значения атрибутов по CSV (не создавая новые атрибуты)

## Допущения (MVP)

- GUID атрибут в блоках называется **`GUID`**.
- Атрибуты в DWG имеют те же имена, что и `ATTR` в CSV.
- Для секций (`attrs_sections.csv`) в DWG блок секции имеет атрибут **`MODE`**:
  - обновляем только строки соответствующего MODE.
- Вариант “две секции = два блока с разными GUID” **не поддерживаем** в MVP.

## Что нужно сделать

### 1) Реализация LISP

Создать:
- `dwg/lisp/import_attrs.lsp`

Поведение:
1. Команда `IMPORT_ATTRS`:
   - запросить у пользователя путь к папке с CSV (например `out/`)
   - загрузить три файла:
     - `attrs_panel.csv`
     - `attrs_circuits.csv`
     - `attrs_sections.csv`
2. Построить словари:
   - `dict_panel[GUID][ATTR]=VALUE`
   - `dict_circuits[GUID][ATTR]=VALUE`
   - `dict_sections[GUID][MODE][ATTR]=VALUE`
3. Пройти по всем `INSERT` в чертеже:
   - если у блока есть атрибут `GUID`:
     - если GUID найден в `dict_panel` и/или `dict_circuits`:
       - обновить соответствующие атрибуты блока (только если атрибут существует у блока)
     - если у блока есть атрибут `MODE`:
       - найти `dict_sections[GUID][MODE]` и обновить атрибуты (если атрибут существует)
   - не создавать новые атрибуты, не менять GUID
   - если VALUE пустой → записать пустую строку (разрешено)
4. Итоговый отчёт в командную строку:
   - `blocks_scanned`
   - `blocks_with_guid`
   - `updated_attrs_count`
   - `blocks_skipped_no_guid`
   - `guid_not_found_in_csv`

### 2) Документация для пользователя

Создать:
- `dwg/lisp/README.md`:
  - как загрузить LISP (`APPLOAD`)
  - как вызвать `IMPORT_ATTRS`
  - где взять CSV (из `tools/export_attributes_csv.py`)
  - примеры структуры CSV

### 3) Контракт дисциплины GUID

Создать:
- `docs/contracts/DWG_GUID_DISCIPLINE.md`:
  - что GUID должен быть уникален и неизменяем
  - где хранится (атрибут `GUID`)
  - ожидания к блоку секции (атрибут `MODE`)
  - что скрипт только обновляет существующие атрибуты

## Ограничения (жёстко)

- Не использовать AutoCAD API/.NET — только AutoLISP.
- Не создавать новые атрибуты.
- Не менять GUID.
- Скрипт не зависит от имени блока.

## Git workflow

1) `git checkout -b feature/cad-adapter` (или `git checkout feature/cad-adapter`)
2) Правки только в `dwg/lisp/*` и `docs/contracts/*`
3) `git add dwg/lisp docs/contracts`
4) `git commit -m "cad: import DWG attrs from CSV by GUID (MVP-0.6)"`

## Проверка

- Ручная проверка в AutoCAD:
  - загрузить `import_attrs.lsp`
  - экспортировать CSV через `tools/export_attributes_csv.py`
  - выполнить `IMPORT_ATTRS` и убедиться, что атрибуты обновились

