from __future__ import annotations

import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _uuid() -> str:
    return str(uuid.uuid4())


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "voltage_drop_smoke.sqlite"
    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON;")
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              version TEXT PRIMARY KEY,
              applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        con.executescript((ROOT / "db" / "migrations" / "0001_init.sql").read_text(encoding="utf-8"))
        con.executescript((ROOT / "db" / "migrations" / "0002_circuits.sql").read_text(encoding="utf-8"))
        con.execute("INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)", ("0001_init",))
        con.execute("INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)", ("0002_circuits",))
        con.executescript((ROOT / "db" / "seed_kr_table.sql").read_text(encoding="utf-8"))
        con.executescript((ROOT / "db" / "seed_cable_sections.sql").read_text(encoding="utf-8"))
        con.commit()
    finally:
        con.close()
    return db_path


def test_run_calc_du_populates_circuit_calc(tmp_path: Path) -> None:
    db_path = _make_db(tmp_path)
    panel_id = _uuid()
    circuit_id = _uuid()

    con = sqlite3.connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO panels (id, name, system_type, u_ll_v, u_ph_v)
            VALUES (?, ?, ?, ?, ?)
            """,
            (panel_id, "VD-PANEL", "3PH", 400.0, 230.0),
        )
        con.execute(
            """
            INSERT INTO circuits (
              id, panel_id, name, phases, neutral_present, unbalance_mode,
              length_m, material, cos_phi, load_kind, i_calc_a
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (circuit_id, panel_id, "C1", 3, 1, "NORMAL", 30.0, "CU", 0.9, "OTHER", 20.0),
        )
        con.commit()
    finally:
        con.close()

    cmd = [
        sys.executable,
        str(ROOT / "tools" / "run_calc.py"),
        "--db",
        str(db_path),
        "--panel-id",
        panel_id,
        "--calc-du",
    ]
    subprocess.run(cmd, check=True, cwd=str(ROOT))

    con = sqlite3.connect(db_path)
    try:
        row = con.execute(
            "SELECT circuit_id FROM circuit_calc WHERE circuit_id = ?",
            (circuit_id,),
        ).fetchone()
        assert row is not None
    finally:
        con.close()
