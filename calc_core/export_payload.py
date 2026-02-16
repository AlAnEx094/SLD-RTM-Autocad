from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _required_float(value: object, field: str, ctx: str) -> float:
    if value is None:
        raise ValueError(f"{field} is NULL for {ctx}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} is not a number for {ctx}") from exc


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Expected a numeric value") from exc


def build_payload(conn: sqlite3.Connection, panel_id: str) -> dict:
    if not isinstance(panel_id, str) or not panel_id.strip():
        raise ValueError("panel_id is required")
    panel_id = panel_id.strip()

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    panel = conn.execute(
        """
        SELECT
          id, name, system_type, u_ll_v, u_ph_v,
          du_limit_lighting_pct, du_limit_other_pct
        FROM panels
        WHERE id = ?
        """,
        (panel_id,),
    ).fetchone()
    if panel is None:
        raise ValueError(f"Panel not found: {panel_id}")

    rtm = conn.execute(
        """
        SELECT pp_kw, qp_kvar, sp_kva, ip_a, kr, ne
        FROM rtm_panel_calc
        WHERE panel_id = ?
        """,
        (panel_id,),
    ).fetchone()
    if rtm is None:
        raise ValueError(f"rtm_panel_calc not found for panel_id={panel_id}")

    bus_sections_rows = conn.execute(
        """
        SELECT id, name
        FROM bus_sections
        WHERE panel_id = ?
        ORDER BY name ASC
        """,
        (panel_id,),
    ).fetchall()

    section_calc_rows = conn.execute(
        """
        SELECT bus_section_id, mode, p_kw, q_kvar, s_kva, i_a
        FROM section_calc
        WHERE panel_id = ?
        """,
        (panel_id,),
    ).fetchall()
    section_calc_by_key: dict[tuple[str, str], dict[str, float]] = {}
    for row in section_calc_rows:
        bus_section_id = str(row["bus_section_id"])
        mode = str(row["mode"])
        ctx = f"section_calc.panel_id={panel_id}, bus_section_id={bus_section_id}, mode={mode}"
        section_calc_by_key[(bus_section_id, mode)] = {
            "pp_kw": _required_float(row["p_kw"], "p_kw", ctx),
            "qp_kvar": _required_float(row["q_kvar"], "q_kvar", ctx),
            "sp_kva": _required_float(row["s_kva"], "s_kva", ctx),
            "ip_a": _required_float(row["i_a"], "i_a", ctx),
        }

    bus_sections_payload = []
    for row in bus_sections_rows:
        bus_section_id = str(row["id"])
        modes: dict[str, dict[str, float]] = {}
        # Feeds v2 uses NORMAL/EMERGENCY; legacy DBs used NORMAL/RESERVE.
        for mode in ("NORMAL", "EMERGENCY", "RESERVE"):
            entry = section_calc_by_key.get((bus_section_id, mode))
            if entry is not None:
                modes[mode] = entry
        bus_sections_payload.append(
            {
                "bus_section_id": bus_section_id,
                "name": str(row["name"]),
                "modes": modes,
            }
        )

    has_phase = any(
        r[1] == "phase"
        for r in conn.execute("PRAGMA table_info(circuits)").fetchall()
    )
    phase_col = "c.phase," if has_phase else ""
    circuits_rows = conn.execute(
        f"""
        SELECT
          c.id AS circuit_id,
          c.name,
          c.phases,
          {phase_col}
          c.length_m,
          c.material,
          c.cos_phi,
          c.load_kind,
          c.i_calc_a AS circuit_i_calc_a,
          cc.circuit_id AS calc_circuit_id,
          cc.du_v,
          cc.du_pct,
          cc.du_limit_pct,
          cc.s_mm2_selected
        FROM circuits c
        LEFT JOIN circuit_calc cc ON cc.circuit_id = c.id
        WHERE c.panel_id = ?
        ORDER BY c.name ASC
        """,
        (panel_id,),
    ).fetchall()

    circuits_payload = []
    for row in circuits_rows:
        circuit_id = str(row["circuit_id"])
        calc_status = "OK" if row["calc_circuit_id"] is not None else "NO_CALC"
        if calc_status == "OK":
            du_v = _optional_float(row["du_v"])
            du_pct = _optional_float(row["du_pct"])
            du_limit_pct = _optional_float(row["du_limit_pct"])
            s_mm2_selected = _optional_float(row["s_mm2_selected"])
        else:
            du_v = None
            du_pct = None
            du_limit_pct = None
            s_mm2_selected = None

        phases = int(row["phases"])
        phase_raw = row["phase"] if has_phase else None
        phase_val = None
        if phases == 1 and phase_raw is not None:
            s = str(phase_raw).strip()
            if s in ("L1", "L2", "L3"):
                phase_val = s

        circuits_payload.append(
            {
                "circuit_id": circuit_id,
                "name": row["name"],
                "phases": phases,
                "phase": phase_val,
                "length_m": _required_float(
                    row["length_m"], "length_m", f"circuits.id={circuit_id}"
                ),
                "material": str(row["material"]),
                "cos_phi": _required_float(
                    row["cos_phi"], "cos_phi", f"circuits.id={circuit_id}"
                ),
                "load_kind": str(row["load_kind"]),
                "calc": {
                    "status": calc_status,
                    "i_calc_a": _required_float(
                        row["circuit_i_calc_a"], "i_calc_a", f"circuits.id={circuit_id}"
                    ),
                    "du_v": du_v,
                    "du_pct": du_pct,
                    "du_limit_pct": du_limit_pct,
                    "s_mm2_selected": s_mm2_selected,
                },
            }
        )

    payload = {
        "version": "0.4",
        "generated_at": _iso_utc_now(),
        "panel": {
            "panel_id": str(panel["id"]),
            "name": str(panel["name"]),
            "system_type": str(panel["system_type"]),
            "u_ll_v": _optional_float(panel["u_ll_v"]),
            "u_ph_v": _optional_float(panel["u_ph_v"]),
            "du_limits": {
                "lighting_pct": _required_float(
                    panel["du_limit_lighting_pct"],
                    "du_limit_lighting_pct",
                    f"panels.id={panel_id}",
                ),
                "other_pct": _required_float(
                    panel["du_limit_other_pct"],
                    "du_limit_other_pct",
                    f"panels.id={panel_id}",
                ),
            },
            "rtm": {
                "pp_kw": _required_float(
                    rtm["pp_kw"], "pp_kw", f"rtm_panel_calc.panel_id={panel_id}"
                ),
                "qp_kvar": _required_float(
                    rtm["qp_kvar"], "qp_kvar", f"rtm_panel_calc.panel_id={panel_id}"
                ),
                "sp_kva": _required_float(
                    rtm["sp_kva"], "sp_kva", f"rtm_panel_calc.panel_id={panel_id}"
                ),
                "ip_a": _required_float(
                    rtm["ip_a"], "ip_a", f"rtm_panel_calc.panel_id={panel_id}"
                ),
                "kr": _required_float(
                    rtm["kr"], "kr", f"rtm_panel_calc.panel_id={panel_id}"
                ),
                "ne": _required_float(
                    rtm["ne"], "ne", f"rtm_panel_calc.panel_id={panel_id}"
                ),
            },
        },
        "bus_sections": bus_sections_payload,
        "circuits": circuits_payload,
        "dwg_contract": {
            "mapping_version": "0.4",
            "block_guid_attr": "GUID",
        },
    }
    return payload
