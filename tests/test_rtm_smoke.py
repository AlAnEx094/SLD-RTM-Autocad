from __future__ import annotations

import math
import sqlite3
import uuid
from pathlib import Path

import pytest

from calc_core.rtm_f636 import run_panel_calc


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
        con.execute("INSERT INTO panels (id, name, u_ll_v) VALUES (?, ?, ?)", (panel_id, "T1", 400.0))

        # Simple row: choose Ki that hits a seeded column to avoid interpolation in smoke.
        # ne=4, Ki=0.80 => Kr=1.00 (seed)
        # P_inst = 4*1 = 4
        # P_demand = 4*0.8*1.0 = 3.2
        # cos_phi=1 => Q=0, S=3.2
        row_id = _uuid()
        con.execute(
            """
            INSERT INTO rtm_input_rows (id, panel_id, pos, name, ne, p_nom_kw, ki, cos_phi)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (row_id, panel_id, 1, "R1", 4, 1.0, 0.80, 1.0),
        )

        con.commit()
    finally:
        con.close()
    return db_path


def test_run_panel_calc_writes_rows_and_totals(tmp_path: Path) -> None:
    db_path = _make_db(tmp_path)

    # Load panel_id from DB
    con = sqlite3.connect(db_path)
    try:
        panel_id = con.execute("SELECT id FROM panels LIMIT 1").fetchone()[0]
    finally:
        con.close()

    res = run_panel_calc(str(db_path), panel_id, note="smoke")
    assert res.panel_id == panel_id

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        # one calc run created
        run = con.execute("SELECT * FROM calc_runs WHERE id = ?", (res.calc_run_id,)).fetchone()
        assert run is not None

        # one calc row written
        calc_rows = con.execute("SELECT * FROM rtm_calc_rows WHERE calc_run_id = ?", (res.calc_run_id,)).fetchall()
        assert len(calc_rows) == 1
        cr = calc_rows[0]
        assert cr["ne_tab"] == 4
        assert cr["ki_clamped"] == pytest.approx(0.80)
        assert cr["kr"] == pytest.approx(1.00)
        assert cr["p_inst_kw"] == pytest.approx(4.0)
        assert cr["p_demand_kw"] == pytest.approx(3.2)
        assert cr["q_demand_kvar"] == pytest.approx(0.0)
        assert cr["s_demand_kva"] == pytest.approx(3.2)

        # totals written
        totals = con.execute(
            "SELECT * FROM rtm_calc_panel_totals WHERE calc_run_id = ?",
            (res.calc_run_id,),
        ).fetchone()
        assert totals is not None
        assert totals["p_inst_total_kw"] == pytest.approx(4.0)
        assert totals["p_demand_total_kw"] == pytest.approx(3.2)
        assert totals["q_demand_total_kvar"] == pytest.approx(0.0)
        assert totals["s_demand_total_kva"] == pytest.approx(3.2)

        # current check
        expected_i = (3.2 * 1000.0) / (math.sqrt(3.0) * 400.0)
        assert totals["i_demand_total_a"] == pytest.approx(expected_i)
    finally:
        con.close()

