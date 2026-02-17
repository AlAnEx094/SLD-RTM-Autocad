from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_migration_adds_circuits_bus_section_id(tmp_path: Path) -> None:
    from tools.run_calc import ensure_migrations

    db_path = tmp_path / "bus_section.sqlite"
    ensure_migrations(db_path)

    con = sqlite3.connect(db_path)
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info(circuits)").fetchall()]
        assert "bus_section_id" in cols
    finally:
        con.close()

