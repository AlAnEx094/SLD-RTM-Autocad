"""i18n smoke: compile/import UI app."""
from __future__ import annotations

import compileall
from pathlib import Path


def test_streamlit_app_compiles() -> None:
    """Compile app/streamlit_app.py and assert success."""
    repo_root = Path(__file__).resolve().parents[1]
    app_file = repo_root / "app" / "streamlit_app.py"
    result = compileall.compile_file(str(app_file), quiet=1)
    assert result is True
