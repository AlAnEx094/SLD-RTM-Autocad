from __future__ import annotations

import sqlite3
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _uuid() -> str:
    return str(uuid.uuid4())


def _read_migration(path: Path) -> str:
    if not path.exists():
        pytest.fail(f"Missing migration file required by MVP-0.3: {path}")
    return path.read_text(encoding="utf-8")


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "section_aggregation.sqlite"
    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON;")
        con.executescript(_read_migration(ROOT / "db" / "migrations" / "0001_init.sql"))
        con.executescript(_read_migration(ROOT / "db" / "migrations" / "0002_circuits.sql"))
        con.executescript(_read_migration(ROOT / "db" / "migrations" / "0003_bus_and_feeds.sql"))
        con.executescript(_read_migration(ROOT / "db" / "migrations" / "0004_section_calc.sql"))
        con.commit()
    finally:
        con.close()
    return db_path


def test_section_aggregation_normal_mode_sums_child_panel_loads(tmp_path: Path) -> None:
    db_path = _make_db(tmp_path)
    parent_panel_id = _uuid()
    child_panel_id = _uuid()
    section_1_id = _uuid()
    section_2_id = _uuid()
    consumer_id = _uuid()

    p_kw = 12.5
    q_kvar = 6.0
    s_kva = 13.9
    i_a = 22.2

    con = sqlite3.connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO panels (id, name, system_type, u_ll_v, u_ph_v)
            VALUES (?, ?, ?, ?, ?)
            """,
            (parent_panel_id, "PARENT", "3PH", 400.0, 230.0),
        )
        con.execute(
            """
            INSERT INTO panels (id, name, system_type, u_ll_v, u_ph_v)
            VALUES (?, ?, ?, ?, ?)
            """,
            (child_panel_id, "CHILD", "3PH", 400.0, 230.0),
        )
        con.execute(
            "INSERT INTO bus_sections (id, panel_id, name) VALUES (?, ?, ?)",
            (section_1_id, parent_panel_id, "S1"),
        )
        con.execute(
            "INSERT INTO bus_sections (id, panel_id, name) VALUES (?, ?, ?)",
            (section_2_id, parent_panel_id, "S2"),
        )
        con.execute(
            """
            INSERT INTO rtm_panel_calc (panel_id, pp_kw, qp_kvar, sp_kva, ip_a, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (child_panel_id, p_kw, q_kvar, s_kva, i_a, "2026-02-15T00:00:00Z"),
        )
        con.execute(
            """
            INSERT INTO consumers (id, panel_id, name, load_ref_type, load_ref_id, notes, p_kw, q_kvar, s_kva, i_a)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (consumer_id, parent_panel_id, "C-CHILD", "RTM_PANEL", child_panel_id, None, None, None, None, None),
        )
        con.execute(
            """
            INSERT INTO consumer_feeds (id, consumer_id, bus_section_id, feed_role)
            VALUES (?, ?, ?, ?)
            """,
            (_uuid(), consumer_id, section_1_id, "NORMAL"),
        )
        con.execute(
            """
            INSERT INTO consumer_feeds (id, consumer_id, bus_section_id, feed_role)
            VALUES (?, ?, ?, ?)
            """,
            (_uuid(), consumer_id, section_2_id, "RESERVE"),
        )
        con.commit()
    finally:
        con.close()

    try:
        from calc_core.section_aggregation import calc_section_loads
    except ImportError as exc:  # pragma: no cover - required by MVP-0.3 contract
        pytest.fail(f"Missing calc_core.section_aggregation.calc_section_loads: {exc}")

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        calc_section_loads(con, parent_panel_id, mode="NORMAL")

        row = con.execute(
            """
            SELECT p_kw, q_kvar, s_kva, i_a
            FROM section_calc
            WHERE panel_id = ? AND bus_section_id = ? AND mode = ?
            """,
            (parent_panel_id, section_1_id, "NORMAL"),
        ).fetchone()
        assert row is not None
        assert row["p_kw"] == pytest.approx(p_kw)
        assert row["q_kvar"] == pytest.approx(q_kvar)
        assert row["s_kva"] == pytest.approx(s_kva)
        assert row["i_a"] == pytest.approx(i_a)

        row_s2 = con.execute(
            """
            SELECT 1
            FROM section_calc
            WHERE panel_id = ? AND bus_section_id = ? AND mode = ?
            """,
            (parent_panel_id, section_2_id, "NORMAL"),
        ).fetchone()
        assert row_s2 is None
    finally:
        con.close()
