from __future__ import annotations

import math
import sqlite3
import uuid
from dataclasses import dataclass

from .kr_resolver import resolve_kr


def _uuid() -> str:
    return str(uuid.uuid4())


def _tan_phi(cos_phi: float) -> float:
    if cos_phi <= 0.0 or cos_phi > 1.0:
        raise ValueError("cos_phi must be in (0, 1]")
    # tan(phi) = tan(arccos(cos_phi))
    return math.tan(math.acos(cos_phi))


@dataclass(frozen=True)
class PanelCalcResult:
    calc_run_id: str
    panel_id: str


def run_panel_calc(db_path: str, panel_id: str, *, note: str | None = None) -> PanelCalcResult:
    """
    Выполняет расчёт Ф636-92 для одного щита:
    - читает ввод из panels + rtm_input_rows
    - создаёт calc_runs
    - пишет rtm_calc_rows и rtm_calc_panel_totals

    Формулы см. docs/contracts/RTM_F636.md.
    """
    con = sqlite3.connect(db_path)
    try:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON;")

        panel = con.execute("SELECT id, u_ll_v FROM panels WHERE id = ?", (panel_id,)).fetchone()
        if panel is None:
            raise ValueError(f"Panel not found: {panel_id}")
        u_ll_v = float(panel["u_ll_v"])
        if u_ll_v <= 0:
            raise ValueError("u_ll_v must be positive")

        input_rows = con.execute(
            """
            SELECT id, pos, name, ne, p_nom_kw, ki, cos_phi
            FROM rtm_input_rows
            WHERE panel_id = ?
            ORDER BY pos ASC
            """,
            (panel_id,),
        ).fetchall()
        if not input_rows:
            raise ValueError(f"No input rows for panel_id={panel_id}")

        calc_run_id = _uuid()
        con.execute(
            "INSERT INTO calc_runs (id, panel_id, note) VALUES (?, ?, ?)",
            (calc_run_id, panel_id, note),
        )

        p_inst_total = 0.0
        p_dem_total = 0.0
        q_dem_total = 0.0
        s_dem_total = 0.0

        for r in input_rows:
            input_row_id = r["id"]
            ne = int(r["ne"])
            p_nom_kw = float(r["p_nom_kw"])
            ki = float(r["ki"])
            cos_phi = float(r["cos_phi"])

            if ne <= 0:
                raise ValueError(f"ne must be positive (row_id={input_row_id})")
            if p_nom_kw < 0:
                raise ValueError(f"p_nom_kw must be >= 0 (row_id={input_row_id})")

            # Installed power
            p_inst_kw = ne * p_nom_kw

            # Kr by strict contract
            kr_res = resolve_kr(db_path, ne, ki)

            # Demand active power
            p_demand_kw = p_inst_kw * ki * kr_res.kr

            # Reactive, apparent, current (3-phase)
            tphi = _tan_phi(cos_phi)
            q_demand_kvar = p_demand_kw * tphi
            s_demand_kva = p_demand_kw / cos_phi
            i_demand_a = (s_demand_kva * 1000.0) / (math.sqrt(3.0) * u_ll_v)

            con.execute(
                """
                INSERT INTO rtm_calc_rows (
                  id, calc_run_id, input_row_id,
                  ki_clamped, ne_tab, kr,
                  p_inst_kw, p_demand_kw, q_demand_kvar, s_demand_kva, i_demand_a
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _uuid(),
                    calc_run_id,
                    input_row_id,
                    kr_res.ki_clamped,
                    kr_res.ne_tab,
                    kr_res.kr,
                    p_inst_kw,
                    p_demand_kw,
                    q_demand_kvar,
                    s_demand_kva,
                    i_demand_a,
                ),
            )

            p_inst_total += p_inst_kw
            p_dem_total += p_demand_kw
            q_dem_total += q_demand_kvar
            s_dem_total += s_demand_kva

        i_dem_total = (s_dem_total * 1000.0) / (math.sqrt(3.0) * u_ll_v)

        con.execute(
            """
            INSERT INTO rtm_calc_panel_totals (
              id, calc_run_id,
              p_inst_total_kw, p_demand_total_kw, q_demand_total_kvar, s_demand_total_kva, i_demand_total_a
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _uuid(),
                calc_run_id,
                p_inst_total,
                p_dem_total,
                q_dem_total,
                s_dem_total,
                i_dem_total,
            ),
        )

        con.commit()
        return PanelCalcResult(calc_run_id=calc_run_id, panel_id=panel_id)
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

