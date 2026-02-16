"""
Phase balance export tests (MVP-BAL v0.1).

Verifies build_payload includes circuits[].phase for 1PH circuits.
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


def test_export_payload_includes_phase_for_1ph_circuit(tmp_path: Path) -> None:
    """
    Build minimal DB so build_payload succeeds: panels, rtm_panel_calc,
    at least one circuit with phases=1 and phase='L2'. Assert payload includes phase.
    """
    from tools.run_calc import ensure_migrations

    try:
        from calc_core.export_payload import build_payload
    except ImportError as exc:
        pytest.skip(f"calc_core.export_payload not available: {exc}")

    db_path = tmp_path / "phase_balance_export.sqlite"
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
            (panel_id, "P-EXPORT", "3PH", 400.0, 230.0),
        )
        con.execute(
            """
            INSERT INTO rtm_panel_calc (
              panel_id, sum_pn, sum_ki_pn, sum_ki_pn_tg, sum_np2,
              ne, kr, pp_kw, qp_kvar, sp_kva, ip_a, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (panel_id, 10.0, 8.0, 6.0, 12.0, 4.0, 1.05, 8.5, 4.2, 9.4, 13.1, "2026-02-16T00:00:00Z"),
        )
        con.execute(
            """
            INSERT INTO circuits (
              id, panel_id, name, phases, neutral_present, unbalance_mode,
              length_m, material, cos_phi, load_kind, i_calc_a, phase
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (circuit_id, panel_id, "C1PH", 1, 1, "NORMAL", 15.0, "CU", 0.9, "OTHER", 10.0, "L2"),
        )
        con.commit()
    finally:
        con.close()

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        payload = build_payload(con, panel_id)
    finally:
        con.close()

    assert "circuits" in payload
    assert len(payload["circuits"]) >= 1
    assert payload["circuits"][0]["phase"] == "L2"
