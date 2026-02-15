from __future__ import annotations

import math
import sqlite3
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from calc_core.voltage_drop import (
    RHO_CU,
    X_PER_M,
    calc_circuit_du,
    calc_du_v,
    effective_du_limit,
    sin_phi,
)


def _uuid() -> str:
    return str(uuid.uuid4())


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "voltage_drop.sqlite"
    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON;")
        con.executescript((ROOT / "db" / "migrations" / "0001_init.sql").read_text(encoding="utf-8"))
        con.executescript((ROOT / "db" / "migrations" / "0002_circuits.sql").read_text(encoding="utf-8"))
        con.executescript((ROOT / "db" / "seed_cable_sections.sql").read_text(encoding="utf-8"))
        con.commit()
    finally:
        con.close()
    return db_path


def _sections_from_db(con: sqlite3.Connection) -> list[float]:
    return [
        float(row[0])
        for row in con.execute("SELECT s_mm2 FROM cable_sections ORDER BY s_mm2 ASC").fetchall()
    ]


def _select_section_expected(
    sections: list[float],
    du_limit_pct: float,
    b: float,
    rho: float,
    x: float,
    length_m: float,
    cos_phi: float,
    i_calc_a: float,
    u0_v: float,
) -> float:
    sin_phi_val = math.sqrt(max(0.0, 1.0 - cos_phi * cos_phi))
    for s_mm2 in sections:
        du_v = calc_du_v(b, rho, x, length_m, s_mm2, cos_phi, sin_phi_val, i_calc_a)
        du_pct = 100.0 * du_v / u0_v
        if du_pct <= du_limit_pct:
            return s_mm2
    return sections[-1]


def test_du_decreases_with_section_and_x_term_affects() -> None:
    length_m = 50.0
    cos_phi = 0.8
    sin_phi_val = sin_phi(cos_phi)
    i_calc_a = 10.0
    b = 2.0  # 1PH => b=2

    du_small = calc_du_v(b, RHO_CU, X_PER_M, length_m, 2.5, cos_phi, sin_phi_val, i_calc_a)
    du_large = calc_du_v(b, RHO_CU, X_PER_M, length_m, 10.0, cos_phi, sin_phi_val, i_calc_a)
    assert du_small > du_large

    du_no_x = calc_du_v(b, RHO_CU, 0.0, length_m, 6.0, cos_phi, sin_phi_val, i_calc_a)
    du_with_x = calc_du_v(b, RHO_CU, X_PER_M, length_m, 6.0, cos_phi, sin_phi_val, i_calc_a)
    assert du_with_x > du_no_x


def test_selects_min_section_by_du_limit_using_seeded_sections(tmp_path: Path) -> None:
    db_path = _make_db(tmp_path)
    con = sqlite3.connect(db_path)
    try:
        panel_id = _uuid()
        circuit_id = _uuid()
        con.execute(
            """
            INSERT INTO panels (id, name, system_type, u_ll_v, u_ph_v, du_limit_other_pct)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (panel_id, "P1", "3PH", 400.0, 230.0, 4.0),
        )
        con.execute(
            """
            INSERT INTO circuits (
              id, panel_id, name, phases, neutral_present, unbalance_mode,
              length_m, material, cos_phi, load_kind, i_calc_a
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (circuit_id, panel_id, "C1", 3, 1, "NORMAL", 30.0, "CU", 0.9, "OTHER", 40.0),
        )
        con.commit()

        sections = _sections_from_db(con)
        expected = _select_section_expected(
            sections=sections,
            du_limit_pct=4.0,
            b=1.0,
            rho=RHO_CU,
            x=X_PER_M,
            length_m=30.0,
            cos_phi=0.9,
            i_calc_a=40.0,
            u0_v=230.0,
        )

        calc_circuit_du(con, circuit_id)
        row = con.execute(
            "SELECT s_mm2_selected, du_pct, du_limit_pct FROM circuit_calc WHERE circuit_id = ?",
            (circuit_id,),
        ).fetchone()
        assert row is not None
        assert row[0] == expected
        assert row[1] <= row[2] + 1e-9
    finally:
        con.close()


def test_b_factor_ratio_for_du_v() -> None:
    length_m = 40.0
    cos_phi = 0.85
    sin_phi_val = sin_phi(cos_phi)
    i_calc_a = 25.0
    s_mm2 = 10.0

    du_b1 = calc_du_v(1.0, RHO_CU, X_PER_M, length_m, s_mm2, cos_phi, sin_phi_val, i_calc_a)
    du_b2 = calc_du_v(2.0, RHO_CU, X_PER_M, length_m, s_mm2, cos_phi, sin_phi_val, i_calc_a)
    assert du_b2 == pytest.approx(2.0 * du_b1)


def test_length_over_100m_increases_effective_limit(tmp_path: Path) -> None:
    db_path = _make_db(tmp_path)
    con = sqlite3.connect(db_path)
    try:
        sections = _sections_from_db(con)
        assert 10.0 in sections

        length_m = 150.0
        base_limit_pct = 5.0
        effective_limit_pct = effective_du_limit(base_limit_pct, length_m)
        assert effective_limit_pct > base_limit_pct

        u0_v = 230.0
        cos_phi = 1.0
        sin_phi_val = 0.0
        b = 2.0  # 1PH
        s_small = 10.0

        target_pct = base_limit_pct + (effective_limit_pct - base_limit_pct) / 2.0
        i_calc_a = (target_pct / 100.0) * u0_v / (b * (RHO_CU * length_m / s_small * cos_phi))

        du_v_small = calc_du_v(b, RHO_CU, X_PER_M, length_m, s_small, cos_phi, sin_phi_val, i_calc_a)
        du_pct_small = 100.0 * du_v_small / u0_v
        assert base_limit_pct < du_pct_small <= effective_limit_pct

        expected_effective = _select_section_expected(
            sections=sections,
            du_limit_pct=effective_limit_pct,
            b=b,
            rho=RHO_CU,
            x=X_PER_M,
            length_m=length_m,
            cos_phi=cos_phi,
            i_calc_a=i_calc_a,
            u0_v=u0_v,
        )
        expected_base = _select_section_expected(
            sections=sections,
            du_limit_pct=base_limit_pct,
            b=b,
            rho=RHO_CU,
            x=X_PER_M,
            length_m=length_m,
            cos_phi=cos_phi,
            i_calc_a=i_calc_a,
            u0_v=u0_v,
        )
        assert expected_effective != expected_base

        panel_id = _uuid()
        circuit_id = _uuid()
        con.execute(
            """
            INSERT INTO panels (id, name, system_type, u_ll_v, u_ph_v, du_limit_other_pct)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (panel_id, "P2", "1PH", 230.0, 230.0, base_limit_pct),
        )
        con.execute(
            """
            INSERT INTO circuits (
              id, panel_id, name, phases, neutral_present, unbalance_mode,
              length_m, material, cos_phi, load_kind, i_calc_a
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (circuit_id, panel_id, "C2", 1, 1, "NORMAL", length_m, "CU", cos_phi, "OTHER", i_calc_a),
        )
        con.commit()

        calc_circuit_du(con, circuit_id)
        row = con.execute(
            "SELECT s_mm2_selected, du_limit_pct FROM circuit_calc WHERE circuit_id = ?",
            (circuit_id,),
        ).fetchone()
        assert row is not None
        assert row[0] == expected_effective
        assert row[1] == pytest.approx(effective_limit_pct)
    finally:
        con.close()
