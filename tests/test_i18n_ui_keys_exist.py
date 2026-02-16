"""i18n UI key coverage: every t("...")/t('...') key exists in RU and EN."""
from __future__ import annotations

import json
import re
from pathlib import Path


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _extract_t_keys(content: str) -> set[str]:
    """Extract i18n keys from t("...") and t('...') calls (string literals only)."""
    # Match t("key") or t('key') - literal strings only, no f-strings or variables
    # Avoid t(f"..."), t(var), t("key" + x), etc.
    pattern = r'\bt\s*\(\s*["\']([^"\']+)["\']\s*'
    return set(re.findall(pattern, content))


def test_ui_keys_exist_in_ru_and_en() -> None:
    """Every t("key")/t('key') in UI sources exists in both RU and EN dicts."""
    repo_root = Path(__file__).resolve().parents[1]
    ru = _load_json(repo_root / "app" / "i18n" / "ru.json")
    en = _load_json(repo_root / "app" / "i18n" / "en.json")
    ru_keys = set(ru.keys())
    en_keys = set(en.keys())

    sources = [
        repo_root / "app" / "streamlit_app.py",
        *sorted((repo_root / "app" / "views").glob("*.py")),
    ]
    all_extracted: set[str] = set()
    for path in sources:
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        all_extracted |= _extract_t_keys(content)

    missing_ru = all_extracted - ru_keys
    missing_en = all_extracted - en_keys
    assert not missing_ru, f"Keys in UI but missing in RU: {sorted(missing_ru)}"
    assert not missing_en, f"Keys in UI but missing in EN: {sorted(missing_en)}"
