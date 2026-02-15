#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
import sqlite3
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Allow running as "python tools/run_calc.py" (so repo root is importable)
sys.path.insert(0, str(ROOT))

from calc_core import run_panel_calc  # noqa: E402
from calc_core.section_aggregation import aggregate_section_loads  # noqa: E402
from calc_core.voltage_drop import calc_panel_du  # noqa: E402


def _uuid() -> str:
    return str(uuid.uuid4())


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def ensure_migrations(db_path: Path) -> None:
    migrations_dir = ROOT / "db" / "migrations"
    migration_files = sorted(migrations_dir.glob("*.sql"))
    if not migration_files:
        raise RuntimeError(f"No migrations found in {migrations_dir}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON;")

        # Ensure schema_migrations exists (bootstrap)
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              version TEXT PRIMARY KEY,
              applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        applied = {
            row[0]
            for row in con.execute("SELECT version FROM schema_migrations").fetchall()
        }

        for mf in migration_files:
            version = mf.stem
            if version in applied:
                continue
            con.executescript(_read_text(mf))
            con.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))

        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def seed_kr_table_if_empty(db_path: Path) -> int:
    seed_sql_path = ROOT / "db" / "seed_kr_table.sql"
    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON;")
        n = con.execute("SELECT COUNT(*) FROM kr_table").fetchone()[0]
        if n and int(n) > 0:
            return int(n)
        con.executescript(_read_text(seed_sql_path))
        con.commit()
        n2 = con.execute("SELECT COUNT(*) FROM kr_table").fetchone()[0]
        return int(n2)
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def seed_cable_sections_if_empty(db_path: Path) -> int:
    seed_sql_path = ROOT / "db" / "seed_cable_sections.sql"
    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON;")
        n = con.execute("SELECT COUNT(*) FROM cable_sections").fetchone()[0]
        if n and int(n) > 0:
            return int(n)
        con.executescript(_read_text(seed_sql_path))
        con.commit()
        n2 = con.execute("SELECT COUNT(*) FROM cable_sections").fetchone()[0]
        return int(n2)
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def get_or_create_panel(
    db_path: Path,
    *,
    panel_id: str | None,
    panel_name: str,
    system_type: str,
    u_ll_v: float | None,
    u_ph_v: float | None,
) -> str:
    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON;")

        if panel_id:
            row = con.execute("SELECT id FROM panels WHERE id = ?", (panel_id,)).fetchone()
            if row:
                return str(row[0])
            con.execute(
                """
                INSERT INTO panels (id, name, system_type, u_ll_v, u_ph_v)
                VALUES (?, ?, ?, ?, ?)
                """,
                (panel_id, panel_name, system_type, u_ll_v, u_ph_v),
            )
            con.commit()
            return panel_id

        row = con.execute("SELECT id FROM panels WHERE name = ? LIMIT 1", (panel_name,)).fetchone()
        if row:
            return str(row[0])

        new_id = _uuid()
        con.execute(
            """
            INSERT INTO panels (id, name, system_type, u_ll_v, u_ph_v)
            VALUES (?, ?, ?, ?, ?)
            """,
            (new_id, panel_name, system_type, u_ll_v, u_ph_v),
        )
        con.commit()
        return new_id
    finally:
        con.close()


def ensure_demo_input_rows(db_path: Path, panel_id: str) -> int:
    """
    Если в щите нет строк ввода, добавляет минимальный демо-набор,
    совместимый с частичным seed kr_table (ne=4).
    """
    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON;")
        n = con.execute(
            "SELECT COUNT(*) FROM rtm_rows WHERE panel_id = ?",
            (panel_id,),
        ).fetchone()[0]
        n = int(n)
        if n > 0:
            return n

        rows = [
            # (name, n, pn_kw, ki, cos_phi, tg_phi)
            ("Демо: группа A (Ki=0.725)", 2, 1.0, 0.725, 0.90, None),
            ("Демо: группа B (Ki=0.750)", 2, 1.0, 0.750, 0.95, None),
        ]
        for name, n_value, pn_kw, ki, cos_phi, tg_phi in rows:
            con.execute(
                """
                INSERT INTO rtm_rows (
                  id, panel_id, name, n, pn_kw, ki, cos_phi, tg_phi,
                  phases, phase_mode, phase_fixed
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _uuid(),
                    panel_id,
                    name,
                    n_value,
                    pn_kw,
                    ki,
                    cos_phi,
                    tg_phi,
                    3,
                    "NONE",
                    None,
                ),
            )

        con.commit()
        n2 = con.execute(
            "SELECT COUNT(*) FROM rtm_rows WHERE panel_id = ?",
            (panel_id,),
        ).fetchone()[0]
        return int(n2)
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run RTM F636 calc and optional voltage drop (ΔU) for one panel (SQLite = truth)."
    )
    ap.add_argument("--db", required=True, help="Path to SQLite DB (e.g. db/project.sqlite)")
    ap.add_argument("--panel-id", default=None, help="Existing panel id (GUID). If absent, panel is resolved/created by name.")
    ap.add_argument("--panel-name", default="MVP_PANEL_1", help="Panel name (used to create/resolve panel).")
    ap.add_argument(
        "--system-type",
        choices=("3PH", "1PH"),
        default="3PH",
        help="Panel system type (default: 3PH).",
    )
    ap.add_argument("--u-ll-v", type=float, default=400.0, help="Line-to-line voltage, V (default: 400).")
    ap.add_argument("--u-ph-v", type=float, default=None, help="Phase voltage, V (default: 230 for 3PH).")
    ap.add_argument("--no-seed-kr", action="store_true", help="Do not seed kr_table when empty.")
    ap.add_argument("--no-demo-input", action="store_true", help="Do not create demo input rows when none exist.")
    ap.add_argument("--calc-du", action="store_true", help="Calculate ΔU for all panel circuits.")
    ap.add_argument(
        "--calc-sections",
        action="store_true",
        help="Aggregate loads per bus section (from consumers).",
    )
    ap.add_argument(
        "--sections-mode",
        choices=("NORMAL", "RESERVE"),
        default="NORMAL",
        help="Consumer feed role for section aggregation (default: NORMAL).",
    )
    args = ap.parse_args()

    db_path = Path(args.db)
    ensure_migrations(db_path)

    if not args.no_seed_kr:
        seed_n = seed_kr_table_if_empty(db_path)
    else:
        seed_n = None

    if args.system_type == "3PH":
        u_ll_v = float(args.u_ll_v)
        u_ph_v = float(args.u_ph_v) if args.u_ph_v is not None else 230.0
    else:
        u_ll_v = float(args.u_ll_v)
        u_ph_v = float(args.u_ph_v) if args.u_ph_v is not None else 230.0

    panel_id = get_or_create_panel(
        db_path,
        panel_id=args.panel_id,
        panel_name=args.panel_name,
        system_type=args.system_type,
        u_ll_v=u_ll_v,
        u_ph_v=u_ph_v,
    )

    if not args.no_demo_input:
        input_n = ensure_demo_input_rows(db_path, panel_id)
    else:
        input_n = None

    res = run_panel_calc(str(db_path), panel_id, note="tools/run_calc.py")

    du_count = None
    section_loads = None
    if args.calc_du:
        seed_cable_sections_if_empty(db_path)
        con = sqlite3.connect(db_path)
        try:
            con.execute("PRAGMA foreign_keys = ON;")
            du_count = calc_panel_du(con, panel_id)
        finally:
            con.close()

    if args.calc_sections:
        con = sqlite3.connect(db_path)
        try:
            con.execute("PRAGMA foreign_keys = ON;")
            section_loads = aggregate_section_loads(
                con, panel_id, mode=args.sections_mode
            )
        finally:
            con.close()

    print("OK")
    print("db:", str(db_path))
    print("panel_id:", panel_id)
    if seed_n is not None:
        print("kr_table_rows:", seed_n)
    if input_n is not None:
        print("input_rows:", input_n)
    print("row_calc_rows:", res.row_count)
    if du_count is not None:
        print("du_circuits_processed:", du_count)
    if section_loads is not None:
        print(f"sections_mode: {args.sections_mode}")
        if not section_loads:
            print("sections: none")
        else:
            for entry in sorted(section_loads.values(), key=lambda item: item.section_name):
                print(
                    "section:",
                    entry.section_name,
                    "P_kw=",
                    round(entry.p_kw, 6),
                    "Q_kvar=",
                    round(entry.q_kvar, 6),
                    "S_kva=",
                    round(entry.s_kva, 6),
                    "I_a=",
                    round(entry.i_a, 6),
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

