from __future__ import annotations

import contextlib
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

INPUT_META_TABLE = "ui_input_meta"

SUBSYSTEM_RTM = "RTM"
SUBSYSTEM_PHASE = "PHASE"
SUBSYSTEM_DU = "DU"
SUBSYSTEM_SECTIONS = "SECTIONS"


@dataclass(frozen=True)
class StatusInfo:
    status: str
    calc_updated_at: str | None = None
    effective_input_at: str | None = None
    reason: str | None = None


def _db_uri(db_path: str | Path, read_only: bool) -> str:
    db_abs = Path(db_path).resolve()
    if not read_only:
        return str(db_abs)
    return f"file:{quote(str(db_abs), safe='/')}?mode=ro"


def connect(db_path: str | Path, *, read_only: bool = False) -> sqlite3.Connection:
    db_uri = _db_uri(db_path, read_only)
    conn = sqlite3.connect(db_uri, uri=read_only)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextlib.contextmanager
def tx(conn: sqlite3.Connection) -> Iterable[sqlite3.Connection]:
    try:
        conn.execute("BEGIN")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(str(r[1]) == column for r in rows)


def list_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {str(r[0]) for r in rows}


def schema_status(conn: sqlite3.Connection) -> dict[str, Any]:
    tables = list_tables(conn)
    required = {
        "panels",
        "rtm_rows",
        "rtm_row_calc",
        "rtm_panel_calc",
        "kr_table",
        "panel_phase_calc",
        "circuits",
        "circuit_calc",
        "cable_sections",
        "bus_sections",
        "consumers",
        "consumer_feeds",
        "section_calc",
    }
    missing = sorted(required - tables)

    # Minimal required columns for MVP-UI v0.1.
    required_columns: dict[str, set[str]] = {
        "panels": {
            "id",
            "name",
            "system_type",
            "u_ll_v",
            "u_ph_v",
            "du_limit_lighting_pct",
            "du_limit_other_pct",
            "installation_type",
        },
        "rtm_rows": {
            "id",
            "panel_id",
            "name",
            "n",
            "pn_kw",
            "ki",
            "cos_phi",
            "tg_phi",
            "phases",
            "phase_mode",
            "phase_fixed",
        },
        "circuits": {
            "id",
            "panel_id",
            "phases",
            "length_m",
            "material",
            "cos_phi",
            "load_kind",
            "i_calc_a",
        },
    }
    missing_columns: dict[str, list[str]] = {}
    for table, cols in required_columns.items():
        if table not in tables:
            continue
        actual = {str(r[1]) for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        missing_for_table = sorted(cols - actual)
        if missing_for_table:
            missing_columns[table] = missing_for_table

    has_migrations = "schema_migrations" in tables
    migrations = []
    if has_migrations:
        migrations = [
            str(r[0]) for r in conn.execute("SELECT version FROM schema_migrations")
        ]
    return {
        "missing_tables": missing,
        "missing_columns": missing_columns,
        "has_migrations": has_migrations,
        "migrations": migrations,
    }


def ensure_ui_input_meta(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ui_input_meta (
          panel_id TEXT NOT NULL,
          subsystem TEXT NOT NULL,
          last_input_at TEXT NOT NULL,
          last_input_source TEXT,
          last_input_note TEXT,
          PRIMARY KEY(panel_id, subsystem)
        )
        """
    )


def get_ui_input_meta(
    conn: sqlite3.Connection, panel_id: str, subsystem: str
) -> str | None:
    if not table_exists(conn, INPUT_META_TABLE):
        return None
    row = conn.execute(
        "SELECT last_input_at FROM ui_input_meta WHERE panel_id = ? AND subsystem = ?",
        (panel_id, subsystem),
    ).fetchone()
    return str(row[0]) if row else None


def touch_ui_input_meta(
    conn: sqlite3.Connection,
    panel_id: str,
    subsystem: str,
    *,
    source: str = "UI",
    note: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO ui_input_meta (panel_id, subsystem, last_input_at, last_input_source, last_input_note)
        VALUES (?, ?, datetime('now'), ?, ?)
        ON CONFLICT(panel_id, subsystem) DO UPDATE SET
          last_input_at = excluded.last_input_at,
          last_input_source = excluded.last_input_source,
          last_input_note = excluded.last_input_note
        """,
        (panel_id, subsystem, source, note),
    )


def get_data_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA data_version").fetchone()[0])


def get_db_mtime(db_path: str | Path) -> float | None:
    try:
        return Path(db_path).stat().st_mtime
    except FileNotFoundError:
        return None


def update_state_after_write(
    state: dict[str, Any], db_path: str | Path, conn: sqlite3.Connection | None = None
) -> None:
    close_conn = False
    if conn is None:
        conn = connect(db_path, read_only=False)
        close_conn = True
    try:
        state["data_version"] = get_data_version(conn)
        state["db_mtime"] = get_db_mtime(db_path)
        state["external_change"] = False
        state["last_write_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    finally:
        if close_conn:
            conn.close()


def list_panels(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, name, system_type, u_ll_v, u_ph_v,
               du_limit_lighting_pct, du_limit_other_pct, installation_type
        FROM panels
        ORDER BY name ASC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def get_panel(conn: sqlite3.Connection, panel_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, name, system_type, u_ll_v, u_ph_v,
               du_limit_lighting_pct, du_limit_other_pct, installation_type
        FROM panels
        WHERE id = ?
        """,
        (panel_id,),
    ).fetchone()
    return dict(row) if row else None


def insert_panel(conn: sqlite3.Connection, data: dict[str, Any]) -> str:
    panel_id = str(data.get("id") or uuid.uuid4())
    conn.execute(
        """
        INSERT INTO panels (
          id, name, system_type, u_ll_v, u_ph_v,
          du_limit_lighting_pct, du_limit_other_pct, installation_type
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            panel_id,
            data["name"],
            data["system_type"],
            data.get("u_ll_v"),
            data.get("u_ph_v"),
            data.get("du_limit_lighting_pct", 3.0),
            data.get("du_limit_other_pct", 5.0),
            data.get("installation_type"),
        ),
    )
    return panel_id


def update_panel(conn: sqlite3.Connection, panel_id: str, data: dict[str, Any]) -> None:
    conn.execute(
        """
        UPDATE panels
        SET name = ?, system_type = ?, u_ll_v = ?, u_ph_v = ?,
            du_limit_lighting_pct = ?, du_limit_other_pct = ?, installation_type = ?
        WHERE id = ?
        """,
        (
            data["name"],
            data["system_type"],
            data.get("u_ll_v"),
            data.get("u_ph_v"),
            data.get("du_limit_lighting_pct", 3.0),
            data.get("du_limit_other_pct", 5.0),
            data.get("installation_type"),
            panel_id,
        ),
    )


def delete_panel(conn: sqlite3.Connection, panel_id: str) -> None:
    conn.execute("DELETE FROM panels WHERE id = ?", (panel_id,))


def panel_dependents(conn: sqlite3.Connection, panel_id: str) -> dict[str, int]:
    def _count(query: str) -> int:
        return int(conn.execute(query, (panel_id,)).fetchone()[0])

    return {
        "rtm_rows": _count("SELECT COUNT(*) FROM rtm_rows WHERE panel_id = ?"),
        "rtm_row_calc": _count(
            "SELECT COUNT(*) FROM rtm_row_calc rc JOIN rtm_rows r ON r.id = rc.row_id WHERE r.panel_id = ?"
        ),
        "rtm_panel_calc": _count(
            "SELECT COUNT(*) FROM rtm_panel_calc WHERE panel_id = ?"
        ),
        "panel_phase_calc": _count(
            "SELECT COUNT(*) FROM panel_phase_calc WHERE panel_id = ?"
        ),
        "circuits": _count("SELECT COUNT(*) FROM circuits WHERE panel_id = ?"),
        "circuit_calc": _count(
            "SELECT COUNT(*) FROM circuit_calc cc JOIN circuits c ON c.id = cc.circuit_id WHERE c.panel_id = ?"
        ),
        "bus_sections": _count("SELECT COUNT(*) FROM bus_sections WHERE panel_id = ?"),
        "consumers": _count("SELECT COUNT(*) FROM consumers WHERE panel_id = ?"),
        "consumer_feeds": _count(
            """
            SELECT COUNT(*)
            FROM consumer_feeds f
            JOIN consumers c ON c.id = f.consumer_id
            WHERE c.panel_id = ?
            """
        ),
        "section_calc": _count(
            "SELECT COUNT(*) FROM section_calc WHERE panel_id = ?"
        ),
    }


def list_rtm_rows_with_calc(conn: sqlite3.Connection, panel_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          r.id,
          r.panel_id,
          r.name,
          r.n,
          r.pn_kw,
          r.ki,
          r.cos_phi,
          r.tg_phi,
          r.phases,
          r.phase_mode,
          r.phase_fixed,
          c.pn_total,
          c.ki_pn,
          c.ki_pn_tg,
          c.n_pn2
        FROM rtm_rows r
        LEFT JOIN rtm_row_calc c ON c.row_id = r.id
        WHERE r.panel_id = ?
        ORDER BY r.name ASC
        """,
        (panel_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_rtm_rows(conn: sqlite3.Connection, panel_id: str, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        row_id = str(row.get("id") or uuid.uuid4())
        conn.execute(
            """
            INSERT INTO rtm_rows (
              id, panel_id, name, n, pn_kw, ki, cos_phi, tg_phi,
              phases, phase_mode, phase_fixed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              name = excluded.name,
              n = excluded.n,
              pn_kw = excluded.pn_kw,
              ki = excluded.ki,
              cos_phi = excluded.cos_phi,
              tg_phi = excluded.tg_phi,
              phases = excluded.phases,
              phase_mode = excluded.phase_mode,
              phase_fixed = excluded.phase_fixed
            """,
            (
                row_id,
                panel_id,
                row["name"],
                row["n"],
                row["pn_kw"],
                row["ki"],
                row.get("cos_phi"),
                row.get("tg_phi"),
                row["phases"],
                row["phase_mode"],
                row.get("phase_fixed"),
            ),
        )


def delete_rtm_rows(conn: sqlite3.Connection, row_ids: Iterable[str]) -> int:
    ids = [str(rid) for rid in row_ids if rid]
    if not ids:
        return 0
    conn.execute(
        f"DELETE FROM rtm_rows WHERE id IN ({','.join(['?'] * len(ids))})",
        ids,
    )
    return len(ids)


def get_rtm_panel_calc(conn: sqlite3.Connection, panel_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT sum_pn, sum_ki_pn, sum_ki_pn_tg, sum_np2, ne, kr,
               pp_kw, qp_kvar, sp_kva, ip_a, updated_at
        FROM rtm_panel_calc
        WHERE panel_id = ?
        """,
        (panel_id,),
    ).fetchone()
    return dict(row) if row else None


def get_panel_phase_calc(conn: sqlite3.Connection, panel_id: str) -> dict[str, Any] | None:
    if not table_exists(conn, "panel_phase_calc"):
        return None
    row = conn.execute(
        """
        SELECT ia_a, ib_a, ic_a, imax_a, iavg_a, unbalance_pct, method, updated_at
        FROM panel_phase_calc
        WHERE panel_id = ?
        """,
        (panel_id,),
    ).fetchone()
    return dict(row) if row else None


def count_table(conn: sqlite3.Connection, table: str, where: str = "", params: tuple[Any, ...] = ()) -> int:
    sql = f"SELECT COUNT(*) FROM {table}"
    if where:
        sql += f" WHERE {where}"
    return int(conn.execute(sql, params).fetchone()[0])


def has_rtm_calc(conn: sqlite3.Connection, panel_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM rtm_panel_calc WHERE panel_id = ?",
        (panel_id,),
    ).fetchone()
    return row is not None


def rtm_row_calc_counts(conn: sqlite3.Connection, panel_id: str) -> tuple[int, int]:
    input_count = count_table(conn, "rtm_rows", "panel_id = ?", (panel_id,))
    calc_count = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM rtm_row_calc rc
            JOIN rtm_rows r ON r.id = rc.row_id
            WHERE r.panel_id = ?
            """,
            (panel_id,),
        ).fetchone()[0]
    )
    return input_count, calc_count


def circuits_calc_counts(conn: sqlite3.Connection, panel_id: str) -> tuple[int, int]:
    input_count = count_table(conn, "circuits", "panel_id = ?", (panel_id,))
    calc_count = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM circuit_calc cc
            JOIN circuits c ON c.id = cc.circuit_id
            WHERE c.panel_id = ?
            """,
            (panel_id,),
        ).fetchone()[0]
    )
    return input_count, calc_count


def section_calc_counts(conn: sqlite3.Connection, panel_id: str, mode: str) -> tuple[int, int]:
    input_count = count_table(conn, "bus_sections", "panel_id = ?", (panel_id,))
    calc_count = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM section_calc
            WHERE panel_id = ? AND mode = ?
            """,
            (panel_id, mode),
        ).fetchone()[0]
    )
    return input_count, calc_count


def _parse_ts(value: str | None) -> float | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S",):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        return None


def _effective_input_at(
    conn: sqlite3.Connection,
    panel_id: str,
    subsystem: str,
    *,
    include_global: bool,
) -> str | None:
    local = get_ui_input_meta(conn, panel_id, subsystem)
    if not include_global:
        return local
    global_value = get_ui_input_meta(conn, "*", subsystem)
    if local is None:
        return global_value
    if global_value is None:
        return local
    local_ts = _parse_ts(local)
    global_ts = _parse_ts(global_value)
    if local_ts is None and global_ts is None:
        return local
    if global_ts is None:
        return local
    if local_ts is None:
        return global_value
    return local if local_ts >= global_ts else global_value


def _calc_updated_at_rtm(conn: sqlite3.Connection, panel_id: str) -> str | None:
    row = conn.execute(
        "SELECT updated_at FROM rtm_panel_calc WHERE panel_id = ?",
        (panel_id,),
    ).fetchone()
    return str(row[0]) if row and row[0] else None


def _calc_updated_at_phase(conn: sqlite3.Connection, panel_id: str) -> str | None:
    row = conn.execute(
        "SELECT updated_at FROM panel_phase_calc WHERE panel_id = ?",
        (panel_id,),
    ).fetchone()
    return str(row[0]) if row and row[0] else None


def _calc_updated_at_du(conn: sqlite3.Connection, panel_id: str) -> str | None:
    row = conn.execute(
        """
        SELECT MIN(updated_at)
        FROM circuit_calc cc
        JOIN circuits c ON c.id = cc.circuit_id
        WHERE c.panel_id = ?
        """,
        (panel_id,),
    ).fetchone()
    return str(row[0]) if row and row[0] else None


def _calc_updated_at_sections(
    conn: sqlite3.Connection, panel_id: str, mode: str
) -> str | None:
    row = conn.execute(
        """
        SELECT MIN(updated_at)
        FROM section_calc
        WHERE panel_id = ? AND mode = ?
        """,
        (panel_id, mode),
    ).fetchone()
    return str(row[0]) if row and row[0] else None


def _consumers_reference_rtm(conn: sqlite3.Connection, panel_id: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM consumers
        WHERE panel_id = ?
          AND load_ref_type IN ('RTM_PANEL', 'RTM_ROW')
        LIMIT 1
        """,
        (panel_id,),
    ).fetchone()
    return row is not None


def rtm_status(
    conn: sqlite3.Connection, panel_id: str, *, external_change: bool
) -> StatusInfo:
    input_count, calc_count = rtm_row_calc_counts(conn, panel_id)
    calc_updated_at = _calc_updated_at_rtm(conn, panel_id)
    if input_count == 0:
        return StatusInfo(status="OK", calc_updated_at=calc_updated_at)
    if calc_updated_at is None or calc_count < input_count:
        return StatusInfo(status="NO_CALC", calc_updated_at=calc_updated_at)
    if external_change:
        return StatusInfo(status="UNKNOWN", calc_updated_at=calc_updated_at, reason="external_change")
    if not table_exists(conn, INPUT_META_TABLE):
        return StatusInfo(status="UNKNOWN", calc_updated_at=calc_updated_at, reason="no_ui_meta")
    effective_input_at = _effective_input_at(
        conn, panel_id, SUBSYSTEM_RTM, include_global=False
    )
    if effective_input_at is None:
        return StatusInfo(
            status="UNKNOWN",
            calc_updated_at=calc_updated_at,
            reason="no_input_meta",
        )
    calc_ts = _parse_ts(calc_updated_at)
    input_ts = _parse_ts(effective_input_at)
    if calc_ts is None or input_ts is None:
        return StatusInfo(
            status="UNKNOWN",
            calc_updated_at=calc_updated_at,
            effective_input_at=effective_input_at,
            reason="bad_timestamp",
        )
    if calc_ts < input_ts:
        return StatusInfo(
            status="STALE",
            calc_updated_at=calc_updated_at,
            effective_input_at=effective_input_at,
        )
    return StatusInfo(
        status="OK",
        calc_updated_at=calc_updated_at,
        effective_input_at=effective_input_at,
    )


def phase_status(
    conn: sqlite3.Connection,
    panel_id: str,
    *,
    system_type: str | None,
    external_change: bool,
) -> StatusInfo:
    if system_type != "1PH":
        return StatusInfo(status="HIDDEN")
    input_count, _ = rtm_row_calc_counts(conn, panel_id)
    calc_updated_at = _calc_updated_at_phase(conn, panel_id)
    if input_count == 0:
        return StatusInfo(status="OK", calc_updated_at=calc_updated_at)
    if calc_updated_at is None:
        return StatusInfo(status="NO_CALC", calc_updated_at=calc_updated_at)
    if external_change:
        return StatusInfo(status="UNKNOWN", calc_updated_at=calc_updated_at, reason="external_change")
    if not table_exists(conn, INPUT_META_TABLE):
        return StatusInfo(status="UNKNOWN", calc_updated_at=calc_updated_at, reason="no_ui_meta")
    effective_input_at = _effective_input_at(
        conn, panel_id, SUBSYSTEM_PHASE, include_global=False
    )
    if effective_input_at is None:
        return StatusInfo(status="UNKNOWN", calc_updated_at=calc_updated_at, reason="no_input_meta")
    calc_ts = _parse_ts(calc_updated_at)
    input_ts = _parse_ts(effective_input_at)
    if calc_ts is None or input_ts is None:
        return StatusInfo(status="UNKNOWN", calc_updated_at=calc_updated_at, reason="bad_timestamp")
    if calc_ts < input_ts:
        return StatusInfo(status="STALE", calc_updated_at=calc_updated_at, effective_input_at=effective_input_at)
    return StatusInfo(status="OK", calc_updated_at=calc_updated_at, effective_input_at=effective_input_at)


def du_status(
    conn: sqlite3.Connection, panel_id: str, *, external_change: bool
) -> StatusInfo:
    input_count, calc_count = circuits_calc_counts(conn, panel_id)
    calc_updated_at = _calc_updated_at_du(conn, panel_id)
    if input_count == 0:
        return StatusInfo(status="OK", calc_updated_at=calc_updated_at)
    if calc_updated_at is None or calc_count < input_count:
        return StatusInfo(status="NO_CALC", calc_updated_at=calc_updated_at)
    if external_change:
        return StatusInfo(status="UNKNOWN", calc_updated_at=calc_updated_at, reason="external_change")
    if not table_exists(conn, INPUT_META_TABLE):
        return StatusInfo(status="UNKNOWN", calc_updated_at=calc_updated_at, reason="no_ui_meta")
    effective_input_at = _effective_input_at(
        conn, panel_id, SUBSYSTEM_DU, include_global=True
    )
    if effective_input_at is None:
        return StatusInfo(status="UNKNOWN", calc_updated_at=calc_updated_at, reason="no_input_meta")
    calc_ts = _parse_ts(calc_updated_at)
    input_ts = _parse_ts(effective_input_at)
    if calc_ts is None or input_ts is None:
        return StatusInfo(status="UNKNOWN", calc_updated_at=calc_updated_at, reason="bad_timestamp")
    if calc_ts < input_ts:
        return StatusInfo(status="STALE", calc_updated_at=calc_updated_at, effective_input_at=effective_input_at)
    return StatusInfo(status="OK", calc_updated_at=calc_updated_at, effective_input_at=effective_input_at)


def sections_status(
    conn: sqlite3.Connection,
    panel_id: str,
    *,
    mode: str,
    external_change: bool,
) -> StatusInfo:
    input_count, calc_count = section_calc_counts(conn, panel_id, mode)
    calc_updated_at = _calc_updated_at_sections(conn, panel_id, mode)
    if input_count == 0:
        return StatusInfo(status="OK", calc_updated_at=calc_updated_at)
    if calc_updated_at is None or calc_count < input_count:
        return StatusInfo(status="NO_CALC", calc_updated_at=calc_updated_at)
    if external_change:
        return StatusInfo(status="UNKNOWN", calc_updated_at=calc_updated_at, reason="external_change")
    if not table_exists(conn, INPUT_META_TABLE):
        return StatusInfo(status="UNKNOWN", calc_updated_at=calc_updated_at, reason="no_ui_meta")
    effective_input_at = _effective_input_at(
        conn, panel_id, SUBSYSTEM_SECTIONS, include_global=False
    )
    if effective_input_at is None:
        return StatusInfo(status="UNKNOWN", calc_updated_at=calc_updated_at, reason="no_input_meta")
    calc_ts = _parse_ts(calc_updated_at)
    input_ts = _parse_ts(effective_input_at)
    if calc_ts is None or input_ts is None:
        return StatusInfo(status="UNKNOWN", calc_updated_at=calc_updated_at, reason="bad_timestamp")
    if _consumers_reference_rtm(conn, panel_id):
        rtm_updated = _calc_updated_at_rtm(conn, panel_id)
        rtm_ts = _parse_ts(rtm_updated)
        if rtm_ts is not None and calc_ts < rtm_ts:
            return StatusInfo(status="STALE", calc_updated_at=calc_updated_at, effective_input_at=effective_input_at)
    if calc_ts < input_ts:
        return StatusInfo(status="STALE", calc_updated_at=calc_updated_at, effective_input_at=effective_input_at)
    return StatusInfo(status="OK", calc_updated_at=calc_updated_at, effective_input_at=effective_input_at)


def project_counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        "panels": count_table(conn, "panels"),
        "rtm_rows": count_table(conn, "rtm_rows"),
        "circuits": count_table(conn, "circuits"),
        "consumers": count_table(conn, "consumers"),
    }


def seed_cable_sections_if_empty(conn: sqlite3.Connection, seed_sql_path: str | Path) -> int:
    n = count_table(conn, "cable_sections")
    if n > 0:
        return n
    sql = Path(seed_sql_path).read_text(encoding="utf-8")
    conn.executescript(sql)
    return count_table(conn, "cable_sections")
