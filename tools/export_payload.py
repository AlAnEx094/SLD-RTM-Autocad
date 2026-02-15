#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from calc_core.export_payload import build_payload  # noqa: E402


def _db_uri(db_path: Path) -> str:
    db_abs = db_path.resolve()
    return f"file:{quote(str(db_abs), safe='/')}?mode=ro"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Export DWG sync payload (v0.4) from SQLite (read-only)."
    )
    ap.add_argument("--db", required=True, help="Path to SQLite DB (e.g. db/project.sqlite)")
    ap.add_argument("--panel-id", required=True, help="Panel id (GUID).")
    ap.add_argument("--out", required=True, help="Output JSON path.")
    args = ap.parse_args()

    db_path = Path(args.db)
    db_uri = _db_uri(db_path)

    con = sqlite3.connect(db_uri, uri=True)
    try:
        payload = build_payload(con, args.panel_id)
    finally:
        con.close()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
