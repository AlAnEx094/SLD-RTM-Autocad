#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path


def _connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con


def _resolve_panel_id(con: sqlite3.Connection, *, panel_id: str | None, panel_name: str | None) -> str:
    if panel_id:
        row = con.execute("SELECT id FROM panels WHERE id = ?", (panel_id,)).fetchone()
        if not row:
            raise ValueError(f"Panel not found: {panel_id}")
        return str(row["id"])
    if panel_name:
        row = con.execute(
            "SELECT id FROM panels WHERE name = ? ORDER BY created_at DESC LIMIT 1",
            (panel_name,),
        ).fetchone()
        if not row:
            raise ValueError(f"Panel not found by name: {panel_name}")
        return str(row["id"])
    raise ValueError("Either panel_id or panel_name must be provided")


def _resolve_calc_run_id(con: sqlite3.Connection, *, panel_id: str, calc_run_id: str | None) -> str:
    if calc_run_id:
        row = con.execute(
            "SELECT id FROM calc_runs WHERE id = ? AND panel_id = ?",
            (calc_run_id, panel_id),
        ).fetchone()
        if not row:
            raise ValueError(f"Calc run not found: {calc_run_id}")
        return str(row["id"])
    row = con.execute(
        "SELECT id FROM calc_runs WHERE panel_id = ? ORDER BY started_at DESC LIMIT 1",
        (panel_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"No calc runs found for panel_id={panel_id}")
    return str(row["id"])


def export_json(db_path: Path, *, panel_id: str, calc_run_id: str, out_path: Path) -> None:
    con = _connect(db_path)
    try:
        panel = con.execute("SELECT * FROM panels WHERE id = ?", (panel_id,)).fetchone()
        run = con.execute("SELECT * FROM calc_runs WHERE id = ?", (calc_run_id,)).fetchone()
        totals = con.execute(
            "SELECT * FROM rtm_calc_panel_totals WHERE calc_run_id = ?",
            (calc_run_id,),
        ).fetchone()
        rows = con.execute(
            """
            SELECT
              i.pos,
              i.name,
              i.ne,
              i.p_nom_kw,
              i.ki AS ki_input,
              i.cos_phi,
              c.ki_clamped,
              c.ne_tab,
              c.kr,
              c.p_inst_kw,
              c.p_demand_kw,
              c.q_demand_kvar,
              c.s_demand_kva,
              c.i_demand_a
            FROM rtm_input_rows i
            JOIN rtm_calc_rows c ON c.input_row_id = i.id
            WHERE i.panel_id = ? AND c.calc_run_id = ?
            ORDER BY i.pos ASC
            """,
            (panel_id, calc_run_id),
        ).fetchall()

        payload = {
            "panel": dict(panel) if panel else None,
            "calc_run": dict(run) if run else None,
            "totals": dict(totals) if totals else None,
            "rows": [dict(r) for r in rows],
        }

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        con.close()


def export_csv(db_path: Path, *, panel_id: str, calc_run_id: str, out_path: Path) -> None:
    con = _connect(db_path)
    try:
        totals = con.execute(
            "SELECT * FROM rtm_calc_panel_totals WHERE calc_run_id = ?",
            (calc_run_id,),
        ).fetchone()
        rows = con.execute(
            """
            SELECT
              i.pos,
              i.name,
              i.ne,
              i.p_nom_kw,
              i.ki AS ki_input,
              i.cos_phi,
              c.ki_clamped,
              c.ne_tab,
              c.kr,
              c.p_inst_kw,
              c.p_demand_kw,
              c.q_demand_kvar,
              c.s_demand_kva,
              c.i_demand_a
            FROM rtm_input_rows i
            JOIN rtm_calc_rows c ON c.input_row_id = i.id
            WHERE i.panel_id = ? AND c.calc_run_id = ?
            ORDER BY i.pos ASC
            """,
            (panel_id, calc_run_id),
        ).fetchall()

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if not rows:
                w.writerow(["(no rows)"])
                return
            headers = list(rows[0].keys())
            w.writerow(headers)
            for r in rows:
                w.writerow([r[h] for h in headers])

            # Totals section (simple key-value)
            if totals:
                w.writerow([])
                w.writerow(["TOTALS"])
                for k in totals.keys():
                    w.writerow([k, totals[k]])
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Export latest (or specified) calc run to JSON/CSV.")
    ap.add_argument("--db", required=True, help="Path to SQLite DB")
    ap.add_argument("--panel-id", default=None, help="Panel GUID")
    ap.add_argument("--panel-name", default=None, help="Panel name (alternative to --panel-id)")
    ap.add_argument("--run-id", default=None, help="Calc run GUID (optional; default: latest for panel)")
    ap.add_argument("--format", choices=["json", "csv"], required=True, help="Export format")
    ap.add_argument("--out", required=True, help="Output file path")
    args = ap.parse_args()

    db_path = Path(args.db)
    out_path = Path(args.out)

    con = _connect(db_path)
    try:
        pid = _resolve_panel_id(con, panel_id=args.panel_id, panel_name=args.panel_name)
        rid = _resolve_calc_run_id(con, panel_id=pid, calc_run_id=args.run_id)
    finally:
        con.close()

    if args.format == "json":
        export_json(db_path, panel_id=pid, calc_run_id=rid, out_path=out_path)
    else:
        export_csv(db_path, panel_id=pid, calc_run_id=rid, out_path=out_path)

    print("OK")
    print("db:", str(db_path))
    print("panel_id:", pid)
    print("calc_run_id:", rid)
    print("out:", str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

