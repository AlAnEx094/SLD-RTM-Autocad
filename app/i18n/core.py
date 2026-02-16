"""
i18n core: load_lang (cached JSON) and t(key, **kwargs).
Uses st.session_state["lang"] (RU/EN), RU default.
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

_I18N_DIR = Path(__file__).resolve().parent
_CACHE: dict[str, dict[str, str]] = {}


def load_lang(lang: str) -> dict[str, str]:
    """Load locale JSON for lang (RU/EN). Cached."""
    if lang not in _CACHE:
        path = _I18N_DIR / f"{lang.lower()}.json"
        if path.exists():
            with path.open(encoding="utf-8") as f:
                _CACHE[lang] = json.load(f)
        else:
            _CACHE[lang] = {}
    return _CACHE[lang]


def t(key: str, **kwargs) -> str:
    """
    Translate key using session_state["lang"] (RU/EN).
    Supports .format(**kwargs). Fallback: return key if missing.
    """
    try:
        lang = st.session_state.get("lang", "RU")
    except Exception:
        lang = "RU"
    strings = load_lang(lang)
    raw = strings.get(key, key)
    if not kwargs:
        return raw
    try:
        return raw.format(**kwargs)
    except (KeyError, ValueError):
        return raw
