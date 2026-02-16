"""
Phase balance algorithm tests (MVP-BAL v0.1).

Tests determinism, DB writes (circuits.phase, panel_phase_balance).
Source: docs/contracts/PHASE_BALANCE_V0_1.md
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


def test_phase_balance_algorithm_determinism_and_db_writes(tmp_path: Path) -> None:
    """
    Create tmp SQLite, apply migrations via ensure_migrations, insert minimal panels
    and multiple 1PH circuits with varying i_calc_a. Call calc_phase_balance.
    Assert: return count, phase in L1/L2/L3, panel_phase_balance exists, determinism.
    """
    from tools.run_calc import ensure_migrations

    try:
        from calc_core.phase_balance import calc_phase_balance
    except ImportError as exc:
        pytest.skip(f"calc_core.phase_balance not available: {exc}")

    db_path = tmp_path / "phase_balance_algorithm.sqlite"
    ensure_migrations(db_path)

    panel_id = _uuid()
    circuit_ids = [_uuid() for _ in range(5)]

    con = sqlite3.connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO panels (id, name, system_type, u_ll_v, u_ph_v)
            VALUES (?, ?, ?, ?, ?)
            """,
            (panel_id, "P1", "3PH", 400.0, 230.0),
        )
        for i, cid in enumerate(circuit_ids):
            i_calc = [12.0, 8.0, 15.0, 6.0, 10.0][i]
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
        count = calc_phase_balance(con, panel_id, mode="NORMAL")
    finally:
        con.close()

    assert count == 5

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        circuits = con.execute(
            "SELECT id, phase FROM circuits WHERE panel_id = ? AND phases = 1",
            (panel_id,),
        ).fetchall()
        for row in circuits:
            assert row["phase"] in ("L1", "L2", "L3"), f"Circuit {row['id']} has invalid phase {row['phase']}"

        balance = con.execute(
            "SELECT i_l1, i_l2, i_l3, unbalance_pct FROM panel_phase_balance WHERE panel_id = ? AND mode = ?",
            (panel_id, "NORMAL"),
        ).fetchone()
        assert balance is not None
        assert isinstance(balance["i_l1"], (int, float))
        assert isinstance(balance["i_l2"], (int, float))
        assert isinstance(balance["i_l3"], (int, float))
        assert isinstance(balance["unbalance_pct"], (int, float))

        phases_first_run = {r["id"]: r["phase"] for r in circuits}

        # Second run: assert same phase assignments (determinism, ignore updated_at)
        calc_phase_balance(con, panel_id, mode="NORMAL")
        con.commit()

        circuits_second = con.execute(
            "SELECT id, phase FROM circuits WHERE panel_id = ? AND phases = 1",
            (panel_id,),
        ).fetchall()
        phases_second_run = {r["id"]: r["phase"] for r in circuits_second}
        assert phases_first_run == phases_second_run
    finally:
        con.close()
