"""
DWG sync scaffold (DB -> DWG).

IMPORTANT (MVP scaffold):
- Does NOT call AutoCAD APIs.
- Does NOT modify DB, calc_core, or db schema.
- Only reads calculated results from SQLite and prints a payload
  representing what would be sent to DWG later.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import quote


@dataclass(frozen=True)
class SyncPayload:
    panel_guid: str
    source_db_path: str
    rtm_panel_calc: Optional[Dict[str, Any]]
    panel_phase_calc: Optional[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "panel_guid": self.panel_guid,
            "source_db_path": self.source_db_path,
            "rtm_panel_calc": self.rtm_panel_calc,
            "panel_phase_calc": self.panel_phase_calc,
        }


class MissingPanelCalcError(RuntimeError):
    def __init__(self, panel_id: str) -> None:
        super().__init__(f"Missing calculated results in rtm_panel_calc for panel_id={panel_id!r}")
        self.panel_id = panel_id


def _connect_ro(db_path: str) -> sqlite3.Connection:
    # Use URI + mode=ro to guarantee read-only access.
    # Note: requires existing file; this is intended.
    abs_path = os.path.abspath(db_path)
    uri = f"file:{quote(abs_path)}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _fetch_one_dict(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> Optional[Dict[str, Any]]:
    cur = conn.execute(sql, params)
    row = cur.fetchone()
    if row is None:
        return None
    return dict(row)


def sync_from_db(db_path: str, panel_id: str) -> None:
    """
    Contract:
      sync_from_db(db_path: str, panel_id: str) -> None

    Reads:
      - rtm_panel_calc (panel totals)
      - panel_phase_calc (phase balance totals)

    Side effect (MVP scaffold):
      Prints JSON payload to stdout.
    """
    if not db_path or not isinstance(db_path, str):
        raise ValueError("db_path must be a non-empty string")
    if not panel_id or not isinstance(panel_id, str):
        raise ValueError("panel_id must be a non-empty string")
    if not os.path.exists(db_path):
        raise FileNotFoundError(db_path)

    with _connect_ro(db_path) as conn:
        rtm_panel_calc = _fetch_one_dict(
            conn,
            "SELECT * FROM rtm_panel_calc WHERE panel_id = ?",
            (panel_id,),
        )
        panel_phase_calc = _fetch_one_dict(
            conn,
            "SELECT * FROM panel_phase_calc WHERE panel_id = ?",
            (panel_id,),
        )

    payload = SyncPayload(
        panel_guid=panel_id,  # Contract: panel_id == DWG panel block GUID
        source_db_path=db_path,
        rtm_panel_calc=rtm_panel_calc,
        panel_phase_calc=panel_phase_calc,
    )

    print(
        json.dumps(
            payload.to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    sys.stdout.flush()

    # Contract note:
    # - payload must still be printed (null fields are allowed)
    # - CLI should exit non-zero with a clear message if panel calc is missing
    if rtm_panel_calc is None:
        raise MissingPanelCalcError(panel_id=panel_id)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="DWG sync scaffold (DB -> DWG). Prints payload JSON.")
    p.add_argument("--db", required=True, help="Path to SQLite DB file")
    p.add_argument("--panel-id", required=True, help="Panel id (also future DWG GUID)")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    ns = _parse_args(argv)
    try:
        sync_from_db(db_path=ns.db, panel_id=ns.panel_id)
        return 0
    except MissingPanelCalcError as e:
        print(f"[cad_adapter] {e}", file=sys.stderr)
        return 4
    except sqlite3.OperationalError as e:
        print(f"[cad_adapter] SQLite operational error: {e}", file=sys.stderr)
        return 2
    except FileNotFoundError:
        print(f"[cad_adapter] DB file not found: {ns.db}", file=sys.stderr)
        return 3
    except Exception as e:
        print(f"[cad_adapter] Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

