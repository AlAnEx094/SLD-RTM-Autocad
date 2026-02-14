from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass

from .kr_resolver import get_kr


def _tan_phi(cos_phi: float) -> float:
    if cos_phi <= 0.0 or cos_phi > 1.0:
        raise ValueError("cos_phi must be in (0, 1]")
    # tan(phi) = tan(arccos(cos_phi))
    return math.tan(math.acos(cos_phi))


def _resolve_tg_phi(tg_phi: float | None, cos_phi: float | None) -> float:
    if tg_phi is not None:
        return float(tg_phi)
    if cos_phi is not None:
        return _tan_phi(float(cos_phi))
    return 0.0


def _calc_current(sp_kva: float, system_type: str, u_ll_v: float | None, u_ph_v: float | None) -> float:
    if system_type == "3PH":
        if u_ll_v is None or u_ll_v <= 0:
            raise ValueError("u_ll_v must be positive for 3PH panels")
        return (sp_kva * 1000.0) / (math.sqrt(3.0) * u_ll_v)
    if system_type == "1PH":
        if u_ph_v is None or u_ph_v <= 0:
            if u_ll_v is None or u_ll_v <= 0:
                raise ValueError("u_ph_v must be positive for 1PH panels")
            u_ph_v = u_ll_v / math.sqrt(3.0)
        return (sp_kva * 1000.0) / u_ph_v
    raise ValueError(f"Unknown system_type: {system_type}")


@dataclass(frozen=True)
class PanelCalcResult:
    panel_id: str
    row_count: int


def run_panel_calc(db_path: str, panel_id: str, *, note: str | None = None) -> PanelCalcResult:
    """
    Выполняет расчёт Ф636-92 для одного щита:
    - читает ввод из panels + rtm_rows
    - пишет расчёт по строкам в rtm_row_calc (upsert)
    - пишет итоги в rtm_panel_calc (upsert)

    Формулы см. docs/contracts/RTM_F636.md.
    """
    _ = note
    con = sqlite3.connect(db_path)
    try:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON;")

        panel = con.execute(
            "SELECT id, system_type, u_ll_v, u_ph_v FROM panels WHERE id = ?",
            (panel_id,),
        ).fetchone()
        if panel is None:
            raise ValueError(f"Panel not found: {panel_id}")
        system_type = str(panel["system_type"])
        u_ll_v = float(panel["u_ll_v"]) if panel["u_ll_v"] is not None else None
        u_ph_v = float(panel["u_ph_v"]) if panel["u_ph_v"] is not None else None

        rows = con.execute(
            """
            SELECT id, n, pn_kw, ki, cos_phi, tg_phi
            FROM rtm_rows
            WHERE panel_id = ?
            ORDER BY name ASC
            """,
            (panel_id,),
        ).fetchall()
        if not rows:
            raise ValueError(f"No input rows for panel_id={panel_id}")

        sum_pn = 0.0
        sum_ki_pn = 0.0
        sum_ki_pn_tg = 0.0
        sum_np2 = 0.0
        pn_kw_max = None

        for r in rows:
            row_id = r["id"]
            n = int(r["n"])
            pn_kw = float(r["pn_kw"])
            ki = float(r["ki"])
            cos_phi = r["cos_phi"]
            tg_phi = r["tg_phi"]

            if n <= 0:
                raise ValueError(f"n must be positive (row_id={row_id})")
            if pn_kw < 0:
                raise ValueError(f"pn_kw must be >= 0 (row_id={row_id})")

            pn_kw_max = pn_kw if pn_kw_max is None else max(pn_kw_max, pn_kw)

            pn_total = n * pn_kw
            ki_pn = ki * pn_total
            tg_val = _resolve_tg_phi(tg_phi, cos_phi)
            ki_pn_tg = ki_pn * tg_val
            n_pn2 = n * pn_kw * pn_kw

            con.execute(
                """
                INSERT INTO rtm_row_calc (row_id, pn_total, ki_pn, ki_pn_tg, n_pn2)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(row_id) DO UPDATE SET
                  pn_total = excluded.pn_total,
                  ki_pn = excluded.ki_pn,
                  ki_pn_tg = excluded.ki_pn_tg,
                  n_pn2 = excluded.n_pn2
                """,
                (row_id, pn_total, ki_pn, ki_pn_tg, n_pn2),
            )

            sum_pn += pn_total
            sum_ki_pn += ki_pn
            sum_ki_pn_tg += ki_pn_tg
            sum_np2 += n_pn2

        if sum_np2 <= 0:
            raise ValueError("sum_np2 must be positive to compute ne")
        if sum_pn <= 0:
            raise ValueError("sum_pn must be positive to compute ki_group")

        ne = (sum_pn * sum_pn) / sum_np2
        ki_group = sum_ki_pn / sum_pn
        kr = get_kr(db_path, ne, ki_group)

        pp_kw = kr * sum_ki_pn
        if pn_kw_max is not None and pp_kw < pn_kw_max:
            pp_kw = pn_kw_max

        qp_kvar = 1.1 * sum_ki_pn_tg if ne <= 10 else sum_ki_pn_tg
        sp_kva = math.sqrt(pp_kw * pp_kw + qp_kvar * qp_kvar)
        ip_a = _calc_current(sp_kva, system_type, u_ll_v, u_ph_v)

        con.execute(
            """
            INSERT INTO rtm_panel_calc (
              panel_id, sum_pn, sum_ki_pn, sum_ki_pn_tg, sum_np2,
              ne, kr, pp_kw, qp_kvar, sp_kva, ip_a, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(panel_id) DO UPDATE SET
              sum_pn = excluded.sum_pn,
              sum_ki_pn = excluded.sum_ki_pn,
              sum_ki_pn_tg = excluded.sum_ki_pn_tg,
              sum_np2 = excluded.sum_np2,
              ne = excluded.ne,
              kr = excluded.kr,
              pp_kw = excluded.pp_kw,
              qp_kvar = excluded.qp_kvar,
              sp_kva = excluded.sp_kva,
              ip_a = excluded.ip_a,
              updated_at = datetime('now')
            """,
            (
                panel_id,
                sum_pn,
                sum_ki_pn,
                sum_ki_pn_tg,
                sum_np2,
                ne,
                kr,
                pp_kw,
                qp_kvar,
                sp_kva,
                ip_a,
            ),
        )

        con.commit()
        return PanelCalcResult(panel_id=panel_id, row_count=len(rows))
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

