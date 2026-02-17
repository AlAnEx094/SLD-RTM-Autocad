"""
Phase balance warnings tests (MVP-BAL v0.1.2).

Ensures invalid MANUAL phases:
- are excluded from sums
- increment invalid_manual_count
- persist non-empty warnings_json
"""

from __future__ import annotations

import json
import sqlite3
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _uuid() -> str:
    return str(uuid.uuid4())


def test_invalid_manual_phase_persists_warnings_and_excluded_from_sums(tmp_path: Path) -> None:
    from tools.run_calc import ensure_migrations
    from calc_core.phase_balance import calc_phase_balance

    db_path = tmp_path / "pb_warn.sqlite"
    ensure_migrations(db_path)

    panel_id = _uuid()
    c_manual_bad = _uuid()
    c_auto_ok = _uuid()

    con = sqlite3.connect(db_path)
    try:
        con.execute(
            "INSERT INTO panels (id, name, system_type, u_ll_v, u_ph_v) VALUES (?, ?, ?, ?, ?)",
            (panel_id, "P1", "3PH", 400.0, 230.0),
        )
        # MANUAL circuit with invalid phase (NULL), high current to catch inclusion bugs
        con.execute(
            """
            INSERT INTO circuits (
              id, panel_id, name, phases, neutral_present, unbalance_mode,
              length_m, material, cos_phi, load_kind, i_calc_a, phase, phase_source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                c_manual_bad,
                panel_id,
                "C_MANUAL_BAD",
                1,
                1,
                "NORMAL",
                10.0,
                "CU",
                0.9,
                "OTHER",
                100.0,
                None,
                "MANUAL",
            ),
        )
        # AUTO circuit
        con.execute(
            """
            INSERT INTO circuits (
              id, panel_id, name, phases, neutral_present, unbalance_mode,
              length_m, material, cos_phi, load_kind, i_calc_a, phase, phase_source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                c_auto_ok,
                panel_id,
                "C_AUTO",
                1,
                1,
                "NORMAL",
                10.0,
                "CU",
                0.9,
                "OTHER",
                10.0,
                None,
                "AUTO",
            ),
        )
        con.commit()
    finally:
        con.close()

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        calc_phase_balance(con, panel_id, mode="NORMAL", respect_manual=True)
    finally:
        con.close()

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            SELECT i_l1, i_l2, i_l3, invalid_manual_count, warnings_json
            FROM panel_phase_balance
            WHERE panel_id = ? AND mode = ?
            """,
            (panel_id, "NORMAL"),
        ).fetchone()
        assert row is not None
        assert int(row["invalid_manual_count"]) == 1
        warnings_json = row["warnings_json"]
        assert warnings_json is not None and str(warnings_json).strip()
        items = json.loads(str(warnings_json))
        assert isinstance(items, list) and len(items) >= 1
        assert any(str(it.get("circuit_id")) == c_manual_bad for it in items if isinstance(it, dict))

        # Manual bad circuit must not be included in sums. Only AUTO circuit (10A) should contribute.
        total = float(row["i_l1"]) + float(row["i_l2"]) + float(row["i_l3"])
        assert total == pytest.approx(10.0, rel=1e-9, abs=1e-9)
    finally:
        con.close()

    # Fix the invalid MANUAL phase and re-run: warnings must auto-clear.
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            "UPDATE circuits SET phase = ? WHERE id = ?",
            ("L1", c_manual_bad),
        )
        con.commit()
    finally:
        con.close()

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        calc_phase_balance(con, panel_id, mode="NORMAL", respect_manual=True)
    finally:
        con.close()

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            SELECT i_l1, i_l2, i_l3, invalid_manual_count, warnings_json
            FROM panel_phase_balance
            WHERE panel_id = ? AND mode = ?
            """,
            (panel_id, "NORMAL"),
        ).fetchone()
        assert row is not None
        assert int(row["invalid_manual_count"]) == 0
        assert row["warnings_json"] is None

        # Now both circuits should be included in sums: 100A (MANUAL) + 10A (AUTO) = 110A.
        total = float(row["i_l1"]) + float(row["i_l2"]) + float(row["i_l3"])
        assert total == pytest.approx(110.0, rel=1e-9, abs=1e-9)
    finally:
        con.close()

