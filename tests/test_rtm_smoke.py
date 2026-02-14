from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from calc_core import rtm_f636


ROOT = Path(__file__).resolve().parents[1]


def _uuid() -> str:
    return str(uuid.uuid4())


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "t.sqlite"
    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON;")
        con.executescript((ROOT / "db" / "migrations" / "0001_init.sql").read_text(encoding="utf-8"))
        con.executescript((ROOT / "db" / "seed_kr_table.sql").read_text(encoding="utf-8"))

        panel_id = _uuid()
        con.execute(
            "INSERT INTO panels (id, name, system_type, u_ll_v, u_ph_v) VALUES (?, ?, ?, ?, ?)",
            (panel_id, "T1", "3PH", 400.0, 230.0),
        )

        # Simple row: choose Ki that hits a seeded column to avoid interpolation in smoke.
        # ne=4, Ki=0.80 => Kr from seed
        row_id = _uuid()
        con.execute(
            """
            INSERT INTO rtm_rows (
              id, panel_id, name, n, pn_kw, ki, cos_phi, tg_phi, phases, phase_mode, phase_fixed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (row_id, panel_id, "R1", 4, 1.0, 0.80, 1.0, 0.0, 3, "NONE", None),
        )

        con.commit()
    finally:
        con.close()
    return db_path


def _run_calc(db_path: Path, panel_id: str):
    if hasattr(rtm_f636, "calc_panel"):
        con = sqlite3.connect(db_path)
        try:
            return rtm_f636.calc_panel(con, panel_id)
        finally:
            con.close()
    return rtm_f636.run_panel_calc(str(db_path), panel_id)


def test_run_panel_calc_writes_rows_and_totals(tmp_path: Path) -> None:
    db_path = _make_db(tmp_path)

    # Load panel_id from DB
    con = sqlite3.connect(db_path)
    try:
        panel_id = con.execute("SELECT id FROM panels LIMIT 1").fetchone()[0]
        row_id = con.execute("SELECT id FROM rtm_rows LIMIT 1").fetchone()[0]
    finally:
        con.close()

    _run_calc(db_path, panel_id)

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        row_calc = con.execute(
            "SELECT * FROM rtm_row_calc WHERE row_id = ?",
            (row_id,),
        ).fetchone()
        assert row_calc is not None

        panel_calc = con.execute(
            "SELECT * FROM rtm_panel_calc WHERE panel_id = ?",
            (panel_id,),
        ).fetchone()
        assert panel_calc is not None
    finally:
        con.close()

