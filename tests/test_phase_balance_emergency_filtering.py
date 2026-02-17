"""
Phase balance v0.3a: EMERGENCY filtering by active emergency bus sections.
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


def _insert_panel(con: sqlite3.Connection, panel_id: str) -> None:
    con.execute(
        "INSERT INTO panels (id, name, system_type, u_ll_v, u_ph_v) VALUES (?, ?, ?, ?, ?)",
        (panel_id, "P1", "3PH", 400.0, 230.0),
    )


def _insert_bus_section(con: sqlite3.Connection, panel_id: str, name: str) -> str:
    bs_id = _uuid()
    con.execute(
        "INSERT INTO bus_sections (id, panel_id, name) VALUES (?, ?, ?)",
        (bs_id, panel_id, name),
    )
    return bs_id


def _insert_1ph_circuit(
    con: sqlite3.Connection,
    panel_id: str,
    circuit_id: str,
    name: str,
    i_calc_a: float,
    *,
    bus_section_id: str | None,
) -> None:
    con.execute(
        """
        INSERT INTO circuits (
          id, panel_id, name, phases, neutral_present, unbalance_mode,
          length_m, material, cos_phi, load_kind, i_calc_a, bus_section_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            circuit_id,
            panel_id,
            name,
            1,
            1,
            "NORMAL",
            10.0,
            "CU",
            0.9,
            "OTHER",
            float(i_calc_a),
            bus_section_id,
        ),
    )


def _insert_section_calc(
    con: sqlite3.Connection, panel_id: str, bus_section_id: str, *, mode: str, s_kva: float, i_a: float
) -> None:
    con.execute(
        """
        INSERT INTO section_calc (panel_id, bus_section_id, mode, p_kw, q_kvar, s_kva, i_a, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(panel_id, bus_section_id, mode) DO UPDATE SET
          p_kw = excluded.p_kw,
          q_kvar = excluded.q_kvar,
          s_kva = excluded.s_kva,
          i_a = excluded.i_a,
          updated_at = excluded.updated_at
        """,
        (panel_id, bus_section_id, mode, 0.0, 0.0, float(s_kva), float(i_a)),
    )


def test_emergency_filters_circuits_by_active_emergency_sections(tmp_path: Path) -> None:
    from tools.run_calc import ensure_migrations
    from calc_core.phase_balance import calc_phase_balance

    db_path = tmp_path / "pb_emergency_filter.sqlite"
    ensure_migrations(db_path)

    panel_id = _uuid()
    c_in = _uuid()
    c_out = _uuid()
    c_null = _uuid()

    con = sqlite3.connect(db_path)
    try:
        _insert_panel(con, panel_id)
        bs_active = _insert_bus_section(con, panel_id, "BS_ACTIVE")
        bs_inactive = _insert_bus_section(con, panel_id, "BS_INACTIVE")

        _insert_1ph_circuit(con, panel_id, c_in, "C_IN", 10.0, bus_section_id=bs_active)
        _insert_1ph_circuit(con, panel_id, c_out, "C_OUT", 100.0, bus_section_id=bs_inactive)
        _insert_1ph_circuit(con, panel_id, c_null, "C_NULL", 50.0, bus_section_id=None)

        # Active EMERGENCY section: non-zero load.
        _insert_section_calc(con, panel_id, bs_active, mode="EMERGENCY", s_kva=1.0, i_a=1.0)
        # Inactive EMERGENCY section: zero load.
        _insert_section_calc(con, panel_id, bs_inactive, mode="EMERGENCY", s_kva=0.0, i_a=0.0)

        con.commit()
    finally:
        con.close()

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        calc_phase_balance(con, panel_id, mode="EMERGENCY", respect_manual=True)
    finally:
        con.close()

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            SELECT i_l1, i_l2, i_l3, invalid_manual_count, warnings_json
            FROM panel_phase_balance
            WHERE panel_id = ? AND mode = 'EMERGENCY'
            """,
            (panel_id,),
        ).fetchone()
        assert row is not None
        total = float(row["i_l1"]) + float(row["i_l2"]) + float(row["i_l3"])
        assert total == pytest.approx(10.0, rel=1e-9, abs=1e-9)
        assert int(row["invalid_manual_count"]) == 0
        assert row["warnings_json"] is None

        phases = {
            r["id"]: r["phase"]
            for r in con.execute(
                "SELECT id, phase FROM circuits WHERE id IN (?, ?, ?) ORDER BY id",
                (c_in, c_out, c_null),
            ).fetchall()
        }
        assert phases[c_in] in ("L1", "L2", "L3")
        assert phases[c_out] is None
        assert phases[c_null] is None
    finally:
        con.close()


def test_emergency_fallback_includes_all_circuits_and_persists_warning(tmp_path: Path) -> None:
    from tools.run_calc import ensure_migrations
    from calc_core.phase_balance import calc_phase_balance

    db_path = tmp_path / "pb_emergency_fallback.sqlite"
    ensure_migrations(db_path)

    panel_id = _uuid()
    c1 = _uuid()
    c2 = _uuid()

    con = sqlite3.connect(db_path)
    try:
        _insert_panel(con, panel_id)
        bs1 = _insert_bus_section(con, panel_id, "BS1")
        _insert_1ph_circuit(con, panel_id, c1, "C1", 10.0, bus_section_id=bs1)
        _insert_1ph_circuit(con, panel_id, c2, "C2", 20.0, bus_section_id=None)
        # No section_calc rows for EMERGENCY -> fallback should apply.
        con.commit()
    finally:
        con.close()

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        calc_phase_balance(con, panel_id, mode="EMERGENCY", respect_manual=True)
    finally:
        con.close()

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            SELECT i_l1, i_l2, i_l3, warnings_json
            FROM panel_phase_balance
            WHERE panel_id = ? AND mode = 'EMERGENCY'
            """,
            (panel_id,),
        ).fetchone()
        assert row is not None
        total = float(row["i_l1"]) + float(row["i_l2"]) + float(row["i_l3"])
        assert total == pytest.approx(30.0, rel=1e-9, abs=1e-9)

        warnings_json = row["warnings_json"]
        assert warnings_json is not None and str(warnings_json).strip()
        items = json.loads(str(warnings_json))
        assert any(
            isinstance(it, dict)
            and str(it.get("reason") or "").strip().upper() == "EMERGENCY_SECTIONS_NOT_COMPUTED"
            for it in items
        )
    finally:
        con.close()

