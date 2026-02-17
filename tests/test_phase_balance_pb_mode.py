"""
Phase balance pb-mode tests (MVP-BAL v0.2).

Ensures phase balance results are persisted per (panel_id, mode).
"""

from __future__ import annotations

import sqlite3
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _uuid() -> str:
    return str(uuid.uuid4())


def test_phase_balance_persists_separate_rows_per_mode(tmp_path: Path) -> None:
    from tools.run_calc import ensure_migrations
    from calc_core.phase_balance import calc_phase_balance

    db_path = tmp_path / "pb_mode.sqlite"
    ensure_migrations(db_path)

    panel_id = _uuid()
    c1 = _uuid()
    c2 = _uuid()

    con = sqlite3.connect(db_path)
    try:
        con.execute(
            "INSERT INTO panels (id, name, system_type, u_ll_v, u_ph_v) VALUES (?, ?, ?, ?, ?)",
            (panel_id, "P1", "3PH", 400.0, 230.0),
        )
        con.executemany(
            """
            INSERT INTO circuits (
              id, panel_id, name, phases, neutral_present, unbalance_mode,
              length_m, material, cos_phi, load_kind, i_calc_a
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (c1, panel_id, "C1", 1, 1, "NORMAL", 10.0, "CU", 0.9, "OTHER", 10.0),
                (c2, panel_id, "C2", 1, 1, "NORMAL", 10.0, "CU", 0.9, "OTHER", 20.0),
            ],
        )
        con.commit()
    finally:
        con.close()

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        calc_phase_balance(con, panel_id, mode="NORMAL", respect_manual=True)
        calc_phase_balance(con, panel_id, mode="EMERGENCY", respect_manual=True)
    finally:
        con.close()

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT mode, i_l1, i_l2, i_l3, unbalance_pct
            FROM panel_phase_balance
            WHERE panel_id = ?
            ORDER BY mode
            """,
            (panel_id,),
        ).fetchall()
        assert [str(r["mode"]) for r in rows] == ["EMERGENCY", "NORMAL"]
        assert len(rows) == 2
    finally:
        con.close()

