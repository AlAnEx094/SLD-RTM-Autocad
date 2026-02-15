from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timezone

RHO_CU = 0.0225
RHO_AL = 0.036
X_PER_M = 0.00008

METHOD_BASE = "GOST_R_50571_5_52_2011_APP_G"
METHOD_MAX_SECTION = f"{METHOD_BASE}_MAX_SECTION"


def sin_phi(cos_phi: float) -> float:
    if not isinstance(cos_phi, (int, float)) or isinstance(cos_phi, bool):
        raise TypeError("cos_phi must be a number")
    cos_val = float(cos_phi)
    if math.isnan(cos_val) or math.isinf(cos_val):
        raise ValueError("cos_phi must be finite")
    if cos_val < 0.0 or cos_val > 1.0:
        raise ValueError("cos_phi must be in [0, 1]")
    return math.sqrt(max(0.0, 1.0 - cos_val * cos_val))


def effective_du_limit(base_limit_pct: float, length_m: float) -> float:
    if not isinstance(base_limit_pct, (int, float)) or isinstance(base_limit_pct, bool):
        raise TypeError("base_limit_pct must be a number")
    if not isinstance(length_m, (int, float)) or isinstance(length_m, bool):
        raise TypeError("length_m must be a number")
    base = float(base_limit_pct)
    length = float(length_m)
    if math.isnan(base) or math.isinf(base):
        raise ValueError("base_limit_pct must be finite")
    if math.isnan(length) or math.isinf(length):
        raise ValueError("length_m must be finite")
    if base < 0.0:
        raise ValueError("base_limit_pct must be >= 0")
    if length < 0.0:
        raise ValueError("length_m must be >= 0")
    if length <= 100.0:
        return base
    extra = min(0.005 * (length - 100.0), 0.5)
    return base + extra


def _b_factor(phases: int, unbalance_mode: str) -> float:
    if phases not in (1, 3):
        raise ValueError("phases must be 1 or 3")
    if unbalance_mode not in ("NORMAL", "FULL_UNBALANCED"):
        raise ValueError("unbalance_mode must be NORMAL or FULL_UNBALANCED")
    if phases == 3 and unbalance_mode == "NORMAL":
        return 1.0
    return 2.0


def calc_du_v(
    b: float,
    rho: float,
    x: float,
    length_m: float,
    s_mm2: float,
    cos_phi: float,
    sin_phi_val: float,
    i_calc_a: float,
) -> float:
    if s_mm2 <= 0:
        raise ValueError("s_mm2 must be > 0")
    if length_m < 0:
        raise ValueError("length_m must be >= 0")
    if i_calc_a < 0:
        raise ValueError("i_calc_a must be >= 0")
    return (
        float(b)
        * ((float(rho) * length_m / s_mm2 * cos_phi) + (float(x) * length_m * sin_phi_val))
        * i_calc_a
    )


def _rho_for_material(material: str) -> float:
    if material == "CU":
        return RHO_CU
    if material == "AL":
        return RHO_AL
    raise ValueError(f"Unsupported material: {material}")


def _effective_du_limit_from_panel(
    load_kind: str,
    du_limit_lighting_pct: float,
    du_limit_other_pct: float,
    length_m: float,
) -> float:
    if load_kind == "LIGHTING":
        base = du_limit_lighting_pct
    elif load_kind == "OTHER":
        base = du_limit_other_pct
    else:
        raise ValueError(f"Unsupported load_kind: {load_kind}")
    return effective_du_limit(base, length_m)


def _select_section(
    sections: list[float],
    du_limit_pct: float,
    b: float,
    rho: float,
    x: float,
    length_m: float,
    cos_phi: float,
    sin_phi_val: float,
    i_calc_a: float,
    u0_v: float,
) -> tuple[float, float, float, str]:
    if not sections:
        raise ValueError("cable_sections is empty")
    chosen = None
    du_v = None
    du_pct = None
    for s_mm2 in sections:
        du_v_candidate = calc_du_v(b, rho, x, length_m, s_mm2, cos_phi, sin_phi_val, i_calc_a)
        du_pct_candidate = 100.0 * du_v_candidate / u0_v
        if du_pct_candidate <= du_limit_pct:
            chosen = s_mm2
            du_v = du_v_candidate
            du_pct = du_pct_candidate
            return chosen, du_v, du_pct, METHOD_BASE
    max_s = sections[-1]
    du_v = calc_du_v(b, rho, x, length_m, max_s, cos_phi, sin_phi_val, i_calc_a)
    du_pct = 100.0 * du_v / u0_v
    return max_s, du_v, du_pct, METHOD_MAX_SECTION


def calc_circuit_du(conn: sqlite3.Connection, circuit_id: str) -> None:
    if not circuit_id:
        raise ValueError("circuit_id is required")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    row = conn.execute(
        """
        SELECT
          c.id AS circuit_id,
          c.phases,
          c.unbalance_mode,
          c.length_m,
          c.material,
          c.cos_phi,
          c.load_kind,
          c.i_calc_a,
          p.u_ph_v,
          p.du_limit_lighting_pct,
          p.du_limit_other_pct
        FROM circuits c
        JOIN panels p ON p.id = c.panel_id
        WHERE c.id = ?
        """,
        (circuit_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Circuit not found: {circuit_id}")

    phases = int(row["phases"])
    unbalance_mode = str(row["unbalance_mode"])
    length_m = float(row["length_m"])
    material = str(row["material"])
    cos_phi = float(row["cos_phi"])
    load_kind = str(row["load_kind"])
    i_calc_a = float(row["i_calc_a"])
    u_ph_v = row["u_ph_v"]
    if u_ph_v is None or float(u_ph_v) <= 0:
        raise ValueError("panel.u_ph_v must be positive to compute du_pct")
    u0_v = float(u_ph_v)

    du_limit_pct = _effective_du_limit_from_panel(
        load_kind=load_kind,
        du_limit_lighting_pct=float(row["du_limit_lighting_pct"]),
        du_limit_other_pct=float(row["du_limit_other_pct"]),
        length_m=length_m,
    )

    b = _b_factor(phases, unbalance_mode)
    rho = _rho_for_material(material)
    sin_phi_val = sin_phi(cos_phi)

    sections = [
        float(r["s_mm2"])
        for r in conn.execute("SELECT s_mm2 FROM cable_sections ORDER BY s_mm2 ASC").fetchall()
    ]
    s_mm2_selected, du_v, du_pct, method = _select_section(
        sections=sections,
        du_limit_pct=du_limit_pct,
        b=b,
        rho=rho,
        x=X_PER_M,
        length_m=length_m,
        cos_phi=cos_phi,
        sin_phi_val=sin_phi_val,
        i_calc_a=i_calc_a,
        u0_v=u0_v,
    )

    updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO circuit_calc (
          circuit_id, i_calc_a, du_v, du_pct, du_limit_pct,
          s_mm2_selected, method, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(circuit_id) DO UPDATE SET
          i_calc_a = excluded.i_calc_a,
          du_v = excluded.du_v,
          du_pct = excluded.du_pct,
          du_limit_pct = excluded.du_limit_pct,
          s_mm2_selected = excluded.s_mm2_selected,
          method = excluded.method,
          updated_at = excluded.updated_at
        """,
        (
            circuit_id,
            i_calc_a,
            du_v,
            du_pct,
            du_limit_pct,
            s_mm2_selected,
            method,
            updated_at,
        ),
    )


def calc_panel_du(conn: sqlite3.Connection, panel_id: str) -> int:
    if not panel_id:
        raise ValueError("panel_id is required")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        rows = conn.execute(
            "SELECT id FROM circuits WHERE panel_id = ? ORDER BY name ASC",
            (panel_id,),
        ).fetchall()
        circuit_ids = [str(r["id"]) for r in rows]
        for circuit_id in circuit_ids:
            calc_circuit_du(conn, circuit_id)
        conn.commit()
        return len(circuit_ids)
    except Exception:
        conn.rollback()
        raise
