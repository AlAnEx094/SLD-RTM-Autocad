from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest


def _require_build_payload():
    try:
        from calc_core.export_payload import build_payload
    except ModuleNotFoundError:
        pytest.skip("calc_core.export_payload is not available")
    return build_payload


def _uuid() -> str:
    return str(uuid.uuid4())


def _apply_migrations(con: sqlite3.Connection) -> None:
    con.execute("PRAGMA foreign_keys = ON;")
    con.executescript((ROOT / "db" / "migrations" / "0001_init.sql").read_text(encoding="utf-8"))
    con.executescript((ROOT / "db" / "migrations" / "0002_circuits.sql").read_text(encoding="utf-8"))
    con.executescript((ROOT / "db" / "migrations" / "0003_bus_and_feeds.sql").read_text(encoding="utf-8"))
    con.executescript((ROOT / "db" / "migrations" / "0004_section_calc.sql").read_text(encoding="utf-8"))


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "export_payload.sqlite"
    con = sqlite3.connect(db_path)
    try:
        _apply_migrations(con)
        con.commit()
    finally:
        con.close()
    return db_path


def _seed_minimal_payload_data(
    con: sqlite3.Connection,
    *,
    panel_id: str,
    section_id_with_calc: str,
    section_id_no_calc: str,
    circuit_id_ok: str,
    circuit_id_no_calc: str,
) -> None:
    con.execute(
        """
        INSERT INTO panels (id, name, system_type, u_ll_v, u_ph_v)
        VALUES (?, ?, ?, ?, ?)
        """,
        (panel_id, "P-EXPORT", "3PH", 400.0, 230.0),
    )
    con.execute(
        """
        INSERT INTO rtm_panel_calc (
          panel_id, sum_pn, sum_ki_pn, sum_ki_pn_tg, sum_np2,
          ne, kr, pp_kw, qp_kvar, sp_kva, ip_a, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (panel_id, 10.0, 8.0, 6.0, 12.0, 4.0, 1.05, 8.5, 4.2, 9.4, 13.1, "2026-02-15T00:00:00Z"),
    )
    con.executemany(
        """
        INSERT INTO bus_sections (id, panel_id, name)
        VALUES (?, ?, ?)
        """,
        [
            (section_id_with_calc, panel_id, "SECTION-A"),
            (section_id_no_calc, panel_id, "SECTION-B"),
        ],
    )
    con.execute(
        """
        INSERT INTO section_calc (
          panel_id, bus_section_id, mode, p_kw, q_kvar, s_kva, i_a, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (panel_id, section_id_with_calc, "NORMAL", 5.0, 2.0, 5.4, 8.0, "2026-02-15T00:00:00Z"),
    )
    con.executemany(
        """
        INSERT INTO circuits (
          id, panel_id, name, phases, neutral_present, unbalance_mode,
          length_m, material, cos_phi, load_kind, i_calc_a
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (circuit_id_ok, panel_id, "C-OK", 3, 1, "NORMAL", 25.0, "CU", 0.9, "OTHER", 20.0),
            (circuit_id_no_calc, panel_id, "C-NO", 1, 1, "NORMAL", 15.0, "AL", 0.95, "LIGHTING", 10.0),
        ],
    )
    con.execute(
        """
        INSERT INTO circuit_calc (
          circuit_id, i_calc_a, du_v, du_pct, du_limit_pct, s_mm2_selected, method, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (circuit_id_ok, 20.0, 3.1, 1.2, 5.0, 2.5, "IEC", "2026-02-15T00:00:00Z"),
    )
    con.commit()


def test_build_payload_smoke(tmp_path: Path) -> None:
    build_payload = _require_build_payload()
    db_path = _make_db(tmp_path)
    panel_id = _uuid()
    section_id_with_calc = _uuid()
    section_id_no_calc = _uuid()
    circuit_id_ok = _uuid()
    circuit_id_no_calc = _uuid()

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        _seed_minimal_payload_data(
            con,
            panel_id=panel_id,
            section_id_with_calc=section_id_with_calc,
            section_id_no_calc=section_id_no_calc,
            circuit_id_ok=circuit_id_ok,
            circuit_id_no_calc=circuit_id_no_calc,
        )
        payload = build_payload(con, panel_id)
    finally:
        con.close()

    assert payload["version"] == "0.4"
    for key in ("generated_at", "panel", "bus_sections", "circuits", "dwg_contract"):
        assert key in payload

    panel = payload["panel"]
    assert panel["panel_id"] == panel_id
    assert "rtm" in panel
    for key in ("pp_kw", "qp_kvar", "sp_kva", "ip_a", "kr", "ne"):
        assert key in panel["rtm"]

    sections = payload["bus_sections"]
    assert len(sections) == 2
    section_map = {section["bus_section_id"]: section for section in sections}
    assert "modes" in section_map[section_id_with_calc]
    assert "NORMAL" in section_map[section_id_with_calc]["modes"]
    assert "NORMAL" not in section_map[section_id_no_calc]["modes"]

    circuits = payload["circuits"]
    assert len(circuits) == 2
    circuit_map = {circuit["circuit_id"]: circuit for circuit in circuits}

    calc_ok = circuit_map[circuit_id_ok]["calc"]
    assert calc_ok["status"] == "OK"

    calc_missing = circuit_map[circuit_id_no_calc]["calc"]
    assert calc_missing["status"] == "NO_CALC"
    assert calc_missing["du_v"] is None
    assert calc_missing["du_pct"] is None
    assert calc_missing["du_limit_pct"] is None
    assert calc_missing["s_mm2_selected"] is None


def test_export_payload_cli_smoke(tmp_path: Path) -> None:
    tool_path = ROOT / "tools" / "export_payload.py"
    if not tool_path.exists():
        pytest.skip("tools/export_payload.py is not available")

    db_path = _make_db(tmp_path)
    panel_id = _uuid()
    section_id_with_calc = _uuid()
    section_id_no_calc = _uuid()
    circuit_id_ok = _uuid()
    circuit_id_no_calc = _uuid()

    con = sqlite3.connect(db_path)
    try:
        _seed_minimal_payload_data(
            con,
            panel_id=panel_id,
            section_id_with_calc=section_id_with_calc,
            section_id_no_calc=section_id_no_calc,
            circuit_id_ok=circuit_id_ok,
            circuit_id_no_calc=circuit_id_no_calc,
        )
    finally:
        con.close()

    out_path = tmp_path / "payload.json"
    cmd = [
        sys.executable,
        str(tool_path),
        "--db",
        str(db_path),
        "--panel-id",
        panel_id,
        "--out",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, cwd=str(ROOT))

    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["version"] == "0.4"
