from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_streamlit_app_compiles() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    app_dir = repo_root / "app"

    result = subprocess.run(
        [sys.executable, "-m", "compileall", str(app_dir)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        "compileall failed for app/.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
