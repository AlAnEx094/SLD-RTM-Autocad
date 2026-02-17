"""
Phase balance respect_manual tests (MVP-BAL v0.1.1).

Tests that respect_manual=True preserves MANUAL phases and
respect_manual=False allows overwriting.
"""

from __future__ import annotations

import sqlite3
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _uuid() -> str:
    return str(uuid.uuid4())


def test_respect_manual_true_preserves_manual_phase(tmp_path: Path) -> None:
    """
    Create tmp DB, apply migrations. Insert panel and 1PH circuits.
    Set one circuit phase='L3' and phase_source='MANUAL'.
    Run calc_phase_balance(conn, panel_id, respect_manual=True).
    Assert that circuit's phase remains 'L3' after run.
    """
    from tools.run_calc import ensure_migrations

    try:
        from calc_core.phase_balance import calc_phase_balance
    except ImportError as exc:
        pytest.skip(f"calc_core.phase_balance not available: {exc}")

    db_path = tmp_path / "respect_manual_true.sqlite"
    ensure_migrations(db_path)

    panel_id = _uuid()
    manual_circuit_id = _uuid()
    auto_circuit_ids = [_uuid(), _uuid()]

    con = sqlite3.connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO panels (id, name, system_type, u_ll_v, u_ph_v)
            VALUES (?, ?, ?, ?, ?)
            """,
            (panel_id, "P1", "3PH", 400.0, 230.0),
        )
        # Manual circuit: L3, phase_source=MANUAL
        con.execute(
            """
            INSERT INTO circuits (
              id, panel_id, name, phases, neutral_present, unbalance_mode,
              length_m, material, cos_phi, load_kind, i_calc_a, phase, phase_source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (manual_circuit_id, panel_id, "C_manual", 1, 1, "NORMAL", 10.0, "CU", 0.9, "OTHER", 10.0, "L3", "MANUAL"),
        )
        # Auto circuits
        for i, cid in enumerate(auto_circuit_ids):
            i_calc = [15.0, 8.0][i]
            con.execute(
                """
                INSERT INTO circuits (
                  id, panel_id, name, phases, neutral_present, unbalance_mode,
                  length_m, material, cos_phi, load_kind, i_calc_a
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cid, panel_id, f"C{i}", 1, 1, "NORMAL", 10.0, "CU", 0.9, "OTHER", i_calc),
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
            "SELECT phase FROM circuits WHERE id = ?",
            (manual_circuit_id,),
        ).fetchone()
        assert row is not None
        assert row["phase"] == "L3", f"MANUAL circuit phase must remain L3, got {row['phase']}"
    finally:
        con.close()


def test_respect_manual_false_can_overwrite(tmp_path: Path) -> None:
    """
    Similar setup; one circuit has phase='L3' and phase_source='MANUAL'.
    Run with respect_manual=False. Assert the algorithm does update that
    circuit's phase (deterministic: L3 -> L2 in this setup).
    """
    from tools.run_calc import ensure_migrations

    try:
        from calc_core.phase_balance import calc_phase_balance
    except ImportError as exc:
        pytest.skip(f"calc_core.phase_balance not available: {exc}")

    db_path = tmp_path / "respect_manual_false.sqlite"
    ensure_migrations(db_path)

    panel_id = _uuid()
    manual_circuit_id = _uuid()
    auto_circuit_ids = [_uuid(), _uuid()]

    con = sqlite3.connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO panels (id, name, system_type, u_ll_v, u_ph_v)
            VALUES (?, ?, ?, ?, ?)
            """,
            (panel_id, "P1", "3PH", 400.0, 230.0),
        )
        # Manual circuit: L3, I=10 (will be reassigned with respect_manual=False)
        con.execute(
            """
            INSERT INTO circuits (
              id, panel_id, name, phases, neutral_present, unbalance_mode,
              length_m, material, cos_phi, load_kind, i_calc_a, phase, phase_source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (manual_circuit_id, panel_id, "C_manual", 1, 1, "NORMAL", 10.0, "CU", 0.9, "OTHER", 10.0, "L3", "MANUAL"),
        )
        # Auto circuits: I=15, I=8. Sorted by I desc: 15, 10, 8. Assignment: 15->L1, 10->L2, 8->L3
        for i, cid in enumerate(auto_circuit_ids):
            i_calc = [15.0, 8.0][i]
            con.execute(
                """
                INSERT INTO circuits (
                  id, panel_id, name, phases, neutral_present, unbalance_mode,
                  length_m, material, cos_phi, load_kind, i_calc_a
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cid, panel_id, f"C{i}", 1, 1, "NORMAL", 10.0, "CU", 0.9, "OTHER", i_calc),
            )
        con.commit()
    finally:
        con.close()

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        calc_phase_balance(con, panel_id, mode="NORMAL", respect_manual=False)
    finally:
        con.close()

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT phase FROM circuits WHERE id = ?",
            (manual_circuit_id,),
        ).fetchone()
        assert row is not None
        # Algorithm: sort by I desc (15, 10, 8). Assign: 15->L1, 10->L2, 8->L3.
        # Manual circuit (I=10) was L3, now becomes L2.
        assert row["phase"] == "L2", f"With respect_manual=False, manual circuit should be reassigned to L2, got {row['phase']}"
    finally:
        con.close()
