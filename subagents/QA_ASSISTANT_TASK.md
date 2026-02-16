# QA_ASSISTANT TASK — i18n RU/EN UI coverage tests

ROLE: QA_ASSISTANT  
BRANCH: `feature/i18n-qa` (создавай изменения и коммиты только здесь)  
SCOPE (разрешено менять): `tests/*`  
SCOPE (запрещено менять): `db/*`, `calc_core/*`, `tools/*`, `app/*`, `docs/*`, `dwg/*`

## Контекст

Нужно гарантировать, что i18n подключён и не деградирует:

- UI должен импортироваться/компилироваться (smoke)
- RU/EN словари должны быть симметричны
- все ключи, используемые в UI через `t("...")`, должны существовать и в `ru.json`, и в `en.json`

Источник требований:

- `docs/ui/I18N_SPEC.md`

## Что нужно сделать (обязательно)

### 1) Smoke test: импорт/компиляция UI (обязательно)

- Добавить тест (например `tests/test_i18n_ui_smoke.py`), который:
  - делает `compileall.compile_file("app/streamlit_app.py", quiet=1)` **или** просто импортирует модуль (без запуска `main()`)
  - проверяет, что импорт проходит без исключений

### 2) Тест симметрии словарей RU/EN (обязательно)

- Добавить тест (например `tests/test_i18n_dictionaries.py`), который:
  - читает `app/i18n/ru.json` и `app/i18n/en.json`
  - проверяет, что множества ключей **равны**
  - проверяет наличие минимального набора ключей из `docs/ui/I18N_SPEC.md` (например `sidebar.db_path`, `sidebar.language`, `nav.db_connect`, …)

### 3) Тест покрытия ключей, используемых в UI (обязательно)

- Добавить тест (например `tests/test_i18n_ui_keys_exist.py`), который:
  - сканирует Python-файлы UI: `app/streamlit_app.py` и `app/views/*.py`
  - извлекает ключи из вызовов вида `t("some.key")` и `t('some.key')`
  - проверяет, что каждый найденный ключ есть и в `ru.json`, и в `en.json`
  - (доп.) проверяет, что в UI нет “сырого” пользовательского текста для sidebar/nav (минимальный sanity-check)

## Acceptance criteria

- Добавлены i18n smoke + dictionary symmetry + key coverage тесты.
- Все тесты проходят (`pytest -q`).

## Git workflow (обязательно)

1) `git checkout -b feature/i18n-qa` (или `git checkout feature/i18n-qa`)
2) Правки только в `tests/*`
3) `git add tests`
4) `git commit -m "test: add i18n UI smoke and dictionary coverage"`

