from __future__ import annotations

import csv
import sqlite3
import subprocess
from pathlib import Path


def _apply_migrations(conn: sqlite3.Connection, root: Path) -> None:
    migrations = [
        "0001_init.sql",
        "0002_circuits.sql",
        "0003_bus_and_feeds.sql",
        "0004_section_calc.sql",
    ]
    for name in migrations:
        sql_path = root / "db" / "migrations" / name
        conn.executescript(sql_path.read_text(encoding="utf-8"))


def _seed_minimal_data(conn: sqlite3.Connection) -> dict[str, list[str] | str]:
    conn.execute("PRAGMA foreign_keys = ON;")
    panel_id = "panel-1"
    conn.execute(
        """
        INSERT INTO panels (id, name, system_type, u_ll_v, u_ph_v)
        VALUES (?, ?, ?, ?, ?)
        """,
        (panel_id, "P-1", "3PH", 400.0, 230.0),
    )
    conn.execute(
        """
        INSERT INTO rtm_panel_calc (
          panel_id, sum_pn, sum_ki_pn, sum_ki_pn_tg, sum_np2,
          ne, kr, pp_kw, qp_kvar, sp_kva, ip_a, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (panel_id, 10.0, 9.0, 3.0, 4.0, 4.0, 1.0, 8.5, 2.1, 8.8, 15.2, "2026-02-15T00:00:00Z"),
    )

    bus_section_ids = ["bus-1", "bus-2"]
    conn.execute(
        "INSERT INTO bus_sections (id, panel_id, name) VALUES (?, ?, ?)",
        (bus_section_ids[0], panel_id, "BS-1"),
    )
    conn.execute(
        "INSERT INTO bus_sections (id, panel_id, name) VALUES (?, ?, ?)",
        (bus_section_ids[1], panel_id, "BS-2"),
    )
    conn.execute(
        """
        INSERT INTO section_calc (
          panel_id, bus_section_id, mode, p_kw, q_kvar, s_kva, i_a, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (panel_id, bus_section_ids[0], "NORMAL", 5.0, 1.2, 5.1, 8.4, "2026-02-15T00:00:00Z"),
    )

    circuit_ids = ["circuit-1", "circuit-2"]
    conn.execute(
        """
        INSERT INTO circuits (
          id, panel_id, name, phases, length_m, material, cos_phi, load_kind, i_calc_a
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (circuit_ids[0], panel_id, "C-1", 1, 10.0, "CU", 0.9, "OTHER", 12.5),
    )
    conn.execute(
        """
        INSERT INTO circuits (
          id, panel_id, name, phases, length_m, material, cos_phi, load_kind, i_calc_a
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (circuit_ids[1], panel_id, "C-2", 1, 20.0, "CU", 0.95, "OTHER", 9.5),
    )
    conn.execute(
        """
        INSERT INTO circuit_calc (
          circuit_id, i_calc_a, du_v, du_pct, du_limit_pct, s_mm2_selected, method, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (circuit_ids[0], 12.5, 1.2, 0.8, 5.0, 2.5, "TEST", "2026-02-15T00:00:00Z"),
    )
    return {"panel_id": panel_id, "circuit_ids": circuit_ids, "bus_section_ids": bus_section_ids}


def _write_mapping(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "panel:",
                "  attributes:",
                "    PP_KW: panel.rtm.pp_kw",
                "    IP_A: panel.rtm.ip_a",
                "circuits:",
                "  attributes:",
                "    CIR_NAME: name",
                "    I_A: calc.i_calc_a",
                "    DU_PCT: calc.du_pct",
                "    S_MM2: calc.s_mm2_selected",
                "sections:",
                "  modes: [NORMAL, RESERVE]",
                "  attributes:",
                "    PP_KW: modes.{MODE}.pp_kw",
                "    IP_A: modes.{MODE}.ip_a",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _read_csv_rows(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    return rows[1:]


def test_export_attributes_csv_smoke(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "project.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        _apply_migrations(conn, root)
        ids = _seed_minimal_data(conn)
        conn.commit()
    finally:
        conn.close()

    mapping_path = tmp_path / "mapping.yaml"
    _write_mapping(mapping_path)
    out_dir = tmp_path / "out"

    cmd = [
        "python3",
        str(root / "tools" / "export_attributes_csv.py"),
        "--db",
        str(db_path),
        "--panel-id",
        str(ids["panel_id"]),
        "--mapping",
        str(mapping_path),
        "--out-dir",
        str(out_dir),
    ]
    subprocess.run(cmd, check=True, cwd=root)

    panel_csv = out_dir / "attrs_panel.csv"
    circuits_csv = out_dir / "attrs_circuits.csv"
    sections_csv = out_dir / "attrs_sections.csv"

    assert panel_csv.exists()
    assert circuits_csv.exists()
    assert sections_csv.exists()

    panel_rows = _read_csv_rows(panel_csv)
    circuits_rows = _read_csv_rows(circuits_csv)
    sections_rows = _read_csv_rows(sections_csv)

    assert any(row[0] == ids["panel_id"] for row in panel_rows)
    assert {row[0] for row in circuits_rows} >= set(ids["circuit_ids"])
    assert {row[0] for row in sections_rows} >= set(ids["bus_section_ids"])

    missing_calc_id = ids["circuit_ids"][1]
    du_pct_rows = [
        row
        for row in circuits_rows
        if row[0] == missing_calc_id and row[1] == "DU_PCT"
    ]
    assert du_pct_rows, "Expected DU_PCT row for circuit without calc"
    assert du_pct_rows[0][2] == ""
