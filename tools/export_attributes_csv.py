#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from calc_core.export_attributes_csv import (  # noqa: E402
    build_rows_from_payload,
    load_mapping,
)
from calc_core.export_payload import build_payload  # noqa: E402


def _db_uri(db_path: Path) -> str:
    db_abs = db_path.resolve()
    return f"file:{quote(str(db_abs), safe='/')}?mode=ro"


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Export DWG block attributes CSV (v0.5) from SQLite (read-only)."
    )
    ap.add_argument("--db", required=True, help="Path to SQLite DB (e.g. db/project.sqlite)")
    ap.add_argument("--panel-id", required=True, help="Panel id (GUID).")
    ap.add_argument(
        "--mapping",
        default="dwg/mapping_v0_5.yaml",
        help="Path to mapping YAML (default: dwg/mapping_v0_5.yaml).",
    )
    ap.add_argument(
        "--out-dir",
        default="out",
        help="Directory to write CSV files (default: out).",
    )
    args = ap.parse_args()

    db_uri = _db_uri(Path(args.db))
    con = sqlite3.connect(db_uri, uri=True)
    try:
        payload = build_payload(con, args.panel_id)
    finally:
        con.close()

    mapping = load_mapping(args.mapping)
    rows = build_rows_from_payload(payload, mapping)

    out_dir = Path(args.out_dir)
    _write_csv(out_dir / "attrs_panel.csv", ["GUID", "ATTR", "VALUE"], rows["panel"])
    _write_csv(
        out_dir / "attrs_circuits.csv", ["GUID", "ATTR", "VALUE"], rows["circuits"]
    )
    _write_csv(
        out_dir / "attrs_sections.csv",
        ["GUID", "MODE", "ATTR", "VALUE"],
        rows["sections"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
