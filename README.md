# SLD-RTM-AutoCAD — MVP-0.1

MVP-0.1: расчёт нагрузок по РТМ 36.18.32.4-92 (форма Ф636-92) для **одного щита**.

## Команды

Запуск расчёта (создаст БД, применит миграции, засеет `kr_table` и при отсутствии ввода добавит демо-строки):

```bash
python tools/run_calc.py --db db/project.sqlite
```

Если в системе нет `python`, используйте:

```bash
python3 tools/run_calc.py --db db/project.sqlite
```

Экспорт результата:

```bash
python3 tools/export_results.py --db db/project.sqlite --panel-name MVP_PANEL_1 --format json --out out/result.json
python3 tools/export_results.py --db db/project.sqlite --panel-name MVP_PANEL_1 --format csv  --out out/result.csv
```

Тесты:

```bash
pytest -q
```

## Контракты

- `docs/contracts/KR_RESOLVER.md` — **жёсткий контракт** вычисления `Kr` из SQLite (clamp/округление/интерполяция).
- `docs/contracts/RTM_F636.md` — MVP-интерпретация расчёта формы Ф636-92.

