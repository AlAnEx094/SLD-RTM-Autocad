from __future__ import annotations

"""
Section aggregation.

Behavior note:
- Legacy (MVP-0.3, Feeds v1): the `mode` argument is interpreted as consumer feed role
  (NORMAL/RESERVE) and the bus section is selected from `consumer_feeds.feed_role`.
- Feeds v2: the `mode` argument is interpreted as calculation mode (NORMAL/EMERGENCY).
  Active feed is selected via `consumer_mode_rules` + `consumer_feeds.feed_role_id`
  ordered by `consumer_feeds.priority` (ascending).

Compatibility aliases (to keep older UI/CLI working during transition):
- For Feeds v2 DB: "RESERVE" is accepted as a deprecated alias for "EMERGENCY".
- For legacy DB: "EMERGENCY" is accepted as a deprecated alias for "RESERVE".

- If a consumer has no matching feed, the row is skipped and a warning is printed
  (no logger infra in MVP).
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
    # Legacy helper kept for backward compatibility inside this module.
    return _normalize_mode(mode, feeds_v2=False)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(str(r[1]) == column for r in rows)


def _feeds_v2_enabled(conn: sqlite3.Connection) -> bool:
    # All of these are introduced by Feeds v2 migrations.
    required_tables = ("feed_roles", "modes", "consumer_mode_rules")
    if not all(_table_exists(conn, t) for t in required_tables):
        return False
    if not _table_exists(conn, "consumer_feeds"):
        return False
    return _column_exists(conn, "consumer_feeds", "feed_role_id") and _column_exists(
        conn, "consumer_feeds", "priority"
    )


def _normalize_mode(mode: str, *, feeds_v2: bool) -> str:
    if not isinstance(mode, str):
        raise TypeError("mode must be a string")
    mode_norm = mode.strip().upper()
    if feeds_v2:
        if mode_norm == "RESERVE":
            return "EMERGENCY"
        if mode_norm not in ("NORMAL", "EMERGENCY"):
            raise ValueError("mode must be NORMAL or EMERGENCY")
        return mode_norm

    # Legacy Feeds v1: mode is effectively feed role.
    if mode_norm == "EMERGENCY":
        return "RESERVE"
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

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    feeds_v2 = _feeds_v2_enabled(conn)
    mode_norm = _normalize_mode(mode, feeds_v2=feeds_v2)

    consumers = conn.execute(
        """
        SELECT
          id AS consumer_id,
          name AS consumer_name,
          load_ref_type,
          load_ref_id,
          p_kw,
          q_kvar,
          s_kva,
          i_a
        FROM consumers
        WHERE panel_id = ?
        ORDER BY name ASC
        """,
        (parent_panel_id,),
    ).fetchall()

    # consumer_id -> (bus_section_id, bus_section_name)
    consumer_section: dict[str, tuple[str, str | None]] = {}

    if feeds_v2:
        # Defaults if consumer_mode_rules row is missing.
        default_role = "MAIN" if mode_norm == "NORMAL" else "RESERVE"

        rules_rows = conn.execute(
            """
            SELECT consumer_id, active_feed_role_id
            FROM consumer_mode_rules
            WHERE mode_id = ?
              AND consumer_id IN (SELECT id FROM consumers WHERE panel_id = ?)
            """,
            (mode_norm, parent_panel_id),
        ).fetchall()
        active_role_by_consumer = {
            str(r["consumer_id"]): str(r["active_feed_role_id"]) for r in rules_rows
        }

        feed_rows = conn.execute(
            """
            SELECT
              f.id AS feed_id,
              f.consumer_id,
              f.bus_section_id,
              bs.name AS bus_section_name,
              f.feed_role_id,
              f.priority
            FROM consumer_feeds f
            LEFT JOIN bus_sections bs ON bs.id = f.bus_section_id
            WHERE f.consumer_id IN (SELECT id FROM consumers WHERE panel_id = ?)
            ORDER BY f.consumer_id ASC, f.priority ASC, f.id ASC
            """,
            (parent_panel_id,),
        ).fetchall()

        best_by_consumer_role: dict[tuple[str, str], tuple[str, str | None]] = {}
        best_any_by_consumer: dict[str, tuple[str, str | None]] = {}

        for fr in feed_rows:
            cid = str(fr["consumer_id"])
            bs_id = fr["bus_section_id"]
            if bs_id is None:
                continue
            bs_id_str = str(bs_id)
            bs_name = fr["bus_section_name"]
            bs_name_str = str(bs_name) if bs_name is not None else None

            if cid not in best_any_by_consumer:
                best_any_by_consumer[cid] = (bs_id_str, bs_name_str)

            role_id = fr["feed_role_id"]
            if role_id is None:
                continue
            key = (cid, str(role_id))
            if key not in best_by_consumer_role:
                best_by_consumer_role[key] = (bs_id_str, bs_name_str)

        for cr in consumers:
            cid = str(cr["consumer_id"])
            active_role = active_role_by_consumer.get(cid, default_role)
            chosen = best_by_consumer_role.get((cid, active_role))

            # Fallback: prefer MAIN if requested role isn't present (e.g. RESERVE missing).
            if chosen is None and active_role != "MAIN":
                chosen = best_by_consumer_role.get((cid, "MAIN"))
            # Final fallback: any feed by min(priority).
            if chosen is None:
                chosen = best_any_by_consumer.get(cid)
            if chosen is not None:
                consumer_section[cid] = chosen
    else:
        # Legacy path: select by v1 consumer_feeds.feed_role = NORMAL|RESERVE.
        feed_role = mode_norm
        rows = conn.execute(
            """
            SELECT
              c.id AS consumer_id,
              c.name AS consumer_name,
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

        seen_consumers: set[str] = set()
        for r in rows:
            cid = str(r["consumer_id"])
            if cid in seen_consumers:
                raise ValueError(
                    f"Multiple feeds for consumer_id={cid} and feed_role={feed_role}"
                )
            seen_consumers.add(cid)
            bs_id = r["bus_section_id"]
            if bs_id is None:
                continue
            bs_name = r["bus_section_name"]
            consumer_section[cid] = (str(bs_id), str(bs_name) if bs_name is not None else None)

    loads: dict[str, SectionLoad] = {}

    for row in consumers:
        consumer_id = str(row["consumer_id"])
        consumer_name = str(row["consumer_name"])

        chosen = consumer_section.get(consumer_id)
        if chosen is None:
            if feeds_v2:
                print(
                    f"WARNING: consumer '{consumer_name}' ({consumer_id}) "
                    f"has no active feed for mode={mode_norm}; skipping"
                )
            else:
                print(
                    f"WARNING: consumer '{consumer_name}' ({consumer_id}) "
                    f"has no {mode_norm} feed; skipping"
                )
            continue
        bus_section_id, bus_section_name = chosen

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

        section_name = bus_section_name if bus_section_name is not None else bus_section_id

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

    feeds_v2 = _feeds_v2_enabled(conn)
    mode_norm = _normalize_mode(mode, feeds_v2=feeds_v2)
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
