"""i18n dictionary symmetry: RU/EN keys match and required keys exist."""
from __future__ import annotations

import json
from pathlib import Path


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def test_ru_en_keys_symmetric() -> None:
    """RU and EN dictionaries have identical key sets."""
    repo_root = Path(__file__).resolve().parents[1]
    ru_path = repo_root / "app" / "i18n" / "ru.json"
    en_path = repo_root / "app" / "i18n" / "en.json"
    ru = _load_json(ru_path)
    en = _load_json(en_path)
    assert set(ru.keys()) == set(en.keys()), (
        f"Key mismatch: RU has {set(ru.keys()) - set(en.keys())!r} not in EN; "
        f"EN has {set(en.keys()) - set(ru.keys())!r} not in RU"
    )


def test_required_keys_present() -> None:
    """Required i18n keys exist in both RU and EN."""
    repo_root = Path(__file__).resolve().parents[1]
    ru_path = repo_root / "app" / "i18n" / "ru.json"
    en_path = repo_root / "app" / "i18n" / "en.json"
    ru = _load_json(ru_path)
    en = _load_json(en_path)
    required = {
        "app.title",
        "sidebar.db_path",
        "sidebar.language",
        "nav.db_connect",
        "access_mode.read_only",
        "status.ok",
    }
    missing_ru = required - set(ru.keys())
    missing_en = required - set(en.keys())
    assert not missing_ru, f"RU missing keys: {missing_ru}"
    assert not missing_en, f"EN missing keys: {missing_en}"
