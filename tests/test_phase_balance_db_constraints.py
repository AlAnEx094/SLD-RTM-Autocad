"""
Phase balance DB constraint tests (MVP-BAL v0.1).

Verifies CHECK constraints on circuits.phase and panel_phase_balance.mode.
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


def test_circuits_phase_check_rejects_l4(tmp_path: Path) -> None:
    """Update circuits.phase='L4' must raise sqlite3.IntegrityError."""
    from tools.run_calc import ensure_migrations

    db_path = tmp_path / "phase_balance_constraints.sqlite"
    ensure_migrations(db_path)

    panel_id = _uuid()
    circuit_id = _uuid()

    con = sqlite3.connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO panels (id, name, system_type, u_ll_v, u_ph_v)
            VALUES (?, ?, ?, ?, ?)
            """,
            (panel_id, "P1", "3PH", 400.0, 230.0),
        )
        con.execute(
            """
            INSERT INTO circuits (
              id, panel_id, name, phases, neutral_present, unbalance_mode,
              length_m, material, cos_phi, load_kind, i_calc_a
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (circuit_id, panel_id, "C1", 1, 1, "NORMAL", 10.0, "CU", 0.9, "OTHER", 12.0),
        )
        con.commit()
    finally:
        con.close()

    con = sqlite3.connect(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("UPDATE circuits SET phase = 'L4' WHERE id = ?", (circuit_id,))
            con.commit()
    finally:
        con.close()


def test_panel_phase_balance_mode_check_rejects_reserve(tmp_path: Path) -> None:
    """Insert panel_phase_balance with mode='RESERVE' must raise sqlite3.IntegrityError."""
    from tools.run_calc import ensure_migrations

    db_path = tmp_path / "phase_balance_constraints2.sqlite"
    ensure_migrations(db_path)

    panel_id = _uuid()

    con = sqlite3.connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO panels (id, name, system_type, u_ll_v, u_ph_v)
            VALUES (?, ?, ?, ?, ?)
            """,
            (panel_id, "P1", "3PH", 400.0, 230.0),
        )
        con.commit()
    finally:
        con.close()

    con = sqlite3.connect(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                """
                INSERT INTO panel_phase_balance (
                  panel_id, mode, i_l1, i_l2, i_l3, unbalance_pct, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (panel_id, "RESERVE", 0.0, 0.0, 0.0, 0.0, "2026-02-16T00:00:00Z"),
            )
            con.commit()
    finally:
        con.close()
