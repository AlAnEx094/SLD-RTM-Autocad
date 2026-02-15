from __future__ import annotations

"""
Section aggregation (MVP-0.3).

Behavior note:
- If a consumer has no feed for the requested mode (NORMAL/RESERVE),
  the row is skipped and a warning is printed (no logger infra).
- Writing to section_calc is attempted only if the table exists; otherwise
  calc_section_loads raises a RuntimeError. Use aggregate_section_loads for
  read-only workflows (e.g. tools/run_calc.py).
"""

import sqlite3
from dataclasses import dataclass


@dataclass
class SectionLoad:
    bus_section_id: str
    section_name: str
    p_kw: float = 0.0
    q_kvar: float = 0.0
    s_kva: float = 0.0
    i_a: float = 0.0


def _resolve_mode(mode: str) -> str:
    if not isinstance(mode, str):
        raise TypeError("mode must be a string")
    mode_norm = mode.strip().upper()
    if mode_norm not in ("NORMAL", "RESERVE"):
        raise ValueError("mode must be NORMAL or RESERVE")
    return mode_norm


def _coerce_float(value: object, field: str, ctx: str) -> float:
    if value is None:
        raise ValueError(f"{field} is NULL for {ctx}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} is not a number for {ctx}") from exc


def _load_from_rtm_panel(conn: sqlite3.Connection, panel_id: str) -> tuple[float, float, float, float]:
    row = conn.execute(
        """
        SELECT pp_kw, qp_kvar, sp_kva, ip_a
        FROM rtm_panel_calc
        WHERE panel_id = ?
        """,
        (panel_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"rtm_panel_calc not found for panel_id={panel_id}")
    p_kw = _coerce_float(row[0], "pp_kw", f"rtm_panel_calc.panel_id={panel_id}")
    q_kvar = _coerce_float(row[1], "qp_kvar", f"rtm_panel_calc.panel_id={panel_id}")
    s_kva = _coerce_float(row[2], "sp_kva", f"rtm_panel_calc.panel_id={panel_id}")
    i_a = _coerce_float(row[3], "ip_a", f"rtm_panel_calc.panel_id={panel_id}")
    return p_kw, q_kvar, s_kva, i_a


def _load_from_manual(row: sqlite3.Row, consumer_id: str) -> tuple[float, float, float, float]:
    ctx = f"consumers.id={consumer_id}"
    p_kw = _coerce_float(row["p_kw"], "p_kw", ctx)
    q_kvar = _coerce_float(row["q_kvar"], "q_kvar", ctx)
    s_kva = _coerce_float(row["s_kva"], "s_kva", ctx)
    i_a = _coerce_float(row["i_a"], "i_a", ctx)
    return p_kw, q_kvar, s_kva, i_a


def aggregate_section_loads(
    conn: sqlite3.Connection,
    parent_panel_id: str,
    *,
    mode: str = "NORMAL",
) -> dict[str, SectionLoad]:
    if not parent_panel_id:
        raise ValueError("parent_panel_id is required")
    feed_role = _resolve_mode(mode)

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    rows = conn.execute(
        """
        SELECT
          c.id AS consumer_id,
          c.name AS consumer_name,
          c.load_ref_type,
          c.load_ref_id,
          c.p_kw,
          c.q_kvar,
          c.s_kva,
          c.i_a,
          f.bus_section_id,
          bs.name AS bus_section_name
        FROM consumers c
        LEFT JOIN consumer_feeds f
          ON f.consumer_id = c.id AND f.feed_role = ?
        LEFT JOIN bus_sections bs
          ON bs.id = f.bus_section_id
        WHERE c.panel_id = ?
        ORDER BY c.name ASC
        """,
        (feed_role, parent_panel_id),
    ).fetchall()

    loads: dict[str, SectionLoad] = {}
    seen_consumers: set[str] = set()

    for row in rows:
        consumer_id = str(row["consumer_id"])
        if consumer_id in seen_consumers:
            raise ValueError(
                f"Multiple feeds for consumer_id={consumer_id} and feed_role={feed_role}"
            )
        seen_consumers.add(consumer_id)

        bus_section_id = row["bus_section_id"]
        if bus_section_id is None:
            consumer_name = row["consumer_name"]
            print(
                f"WARNING: consumer '{consumer_name}' ({consumer_id}) "
                f"has no {feed_role} feed; skipping"
            )
            continue

        load_ref_type = row["load_ref_type"]
        load_ref_id = row["load_ref_id"]
        if load_ref_type == "RTM_PANEL":
            if not load_ref_id:
                raise ValueError(f"load_ref_id is required for consumer_id={consumer_id}")
            p_kw, q_kvar, s_kva, i_a = _load_from_rtm_panel(conn, str(load_ref_id))
        elif load_ref_type == "MANUAL":
            p_kw, q_kvar, s_kva, i_a = _load_from_manual(row, consumer_id)
        elif load_ref_type == "RTM_ROW":
            raise NotImplementedError(
                f"RTM_ROW load_ref_type is not supported (consumer_id={consumer_id})"
            )
        else:
            raise ValueError(
                f"Unsupported load_ref_type={load_ref_type} (consumer_id={consumer_id})"
            )

        bus_section_id = str(bus_section_id)
        section_name = row["bus_section_name"]
        if section_name is None:
            section_name = bus_section_id
        else:
            section_name = str(section_name)

        entry = loads.get(bus_section_id)
        if entry is None:
            entry = SectionLoad(
                bus_section_id=bus_section_id,
                section_name=section_name,
                p_kw=0.0,
                q_kvar=0.0,
                s_kva=0.0,
                i_a=0.0,
            )
            loads[bus_section_id] = entry

        entry.p_kw += p_kw
        entry.q_kvar += q_kvar
        entry.s_kva += s_kva
        entry.i_a += i_a

    return loads


def _section_calc_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='section_calc'"
    ).fetchone()
    return row is not None


def _ensure_section_calc_columns(conn: sqlite3.Connection) -> None:
    cols = conn.execute("PRAGMA table_info(section_calc)").fetchall()
    col_names = {str(c[1]) for c in cols}
    required = {
        "panel_id",
        "bus_section_id",
        "mode",
        "p_kw",
        "q_kvar",
        "s_kva",
        "i_a",
    }
    missing = sorted(required - col_names)
    if missing:
        raise ValueError(f"section_calc is missing columns: {', '.join(missing)}")


def calc_section_loads(
    conn: sqlite3.Connection,
    parent_panel_id: str,
    mode: str = "NORMAL",
) -> int:
    """
    Aggregates loads per bus section and upserts into section_calc if available.
    Returns number of sections written.
    """
    loads = aggregate_section_loads(conn, parent_panel_id, mode=mode)
    if not loads:
        return 0

    if not _section_calc_exists(conn):
        raise RuntimeError("section_calc table does not exist; cannot persist results")

    _ensure_section_calc_columns(conn)

    mode_norm = _resolve_mode(mode)
    for entry in loads.values():
        conn.execute(
            """
            INSERT INTO section_calc (
              panel_id, bus_section_id, mode, p_kw, q_kvar, s_kva, i_a, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(panel_id, bus_section_id, mode) DO UPDATE SET
              p_kw = excluded.p_kw,
              q_kvar = excluded.q_kvar,
              s_kva = excluded.s_kva,
              i_a = excluded.i_a,
              updated_at = datetime('now')
            """,
            (
                parent_panel_id,
                entry.bus_section_id,
                mode_norm,
                entry.p_kw,
                entry.q_kvar,
                entry.s_kva,
                entry.i_a,
            ),
        )

    conn.commit()
    return len(loads)
