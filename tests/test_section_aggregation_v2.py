"""Section aggregation v2 tests: mode NORMAL/EMERGENCY with feed_role_id and consumer_mode_rules."""

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
        pytest.fail(f"Missing migration file: {path}")
    return path.read_text(encoding="utf-8")


def _make_db_v2(tmp_path: Path) -> Path:
    """Create DB with migrations 0001..0006 applied."""
    db_path = tmp_path / "section_aggregation_v2.sqlite"
    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON;")
        migrations_dir = ROOT / "db" / "migrations"
        for name in [
            "0001_init.sql",
            "0002_circuits.sql",
            "0003_bus_and_feeds.sql",
            "0004_section_calc.sql",
            "0005_feeds_v2_refs.sql",
            "0006_section_calc_mode_emergency.sql",
        ]:
            con.executescript(_read_migration(migrations_dir / name))
        con.commit()
    finally:
        con.close()
    return db_path


def test_section_aggregation_v2_normal_mode_loads_in_main_section_only(tmp_path: Path) -> None:
    """
    Consumer with MAIN->S1 and RESERVE->S2.
    mode=NORMAL => load only in S1; S2 has no row.
    """
    db_path = _make_db_v2(tmp_path)
    parent_panel_id = _uuid()
    child_panel_id = _uuid()
    section_s1_id = _uuid()
    section_s2_id = _uuid()
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
            (section_s1_id, parent_panel_id, "S1"),
        )
        con.execute(
            "INSERT INTO bus_sections (id, panel_id, name) VALUES (?, ?, ?)",
            (section_s2_id, parent_panel_id, "S2"),
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
        # Feeds v2: feed_role_id MAIN->S1, RESERVE->S2
        con.execute(
            """
            INSERT INTO consumer_feeds (id, consumer_id, bus_section_id, feed_role, feed_role_id, priority)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (_uuid(), consumer_id, section_s1_id, "NORMAL", "MAIN", 1),
        )
        con.execute(
            """
            INSERT INTO consumer_feeds (id, consumer_id, bus_section_id, feed_role, feed_role_id, priority)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (_uuid(), consumer_id, section_s2_id, "RESERVE", "RESERVE", 1),
        )
        # Default consumer_mode_rules from migration 0005: NORMAL->MAIN, EMERGENCY->RESERVE
        con.commit()
    finally:
        con.close()

    try:
        from calc_core.section_aggregation import calc_section_loads
    except ImportError as exc:
        pytest.fail(f"Missing calc_core.section_aggregation.calc_section_loads: {exc}")

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        calc_section_loads(con, parent_panel_id, mode="NORMAL")

        row_s1 = con.execute(
            """
            SELECT p_kw, q_kvar, s_kva, i_a
            FROM section_calc
            WHERE panel_id = ? AND bus_section_id = ? AND mode = ?
            """,
            (parent_panel_id, section_s1_id, "NORMAL"),
        ).fetchone()
        assert row_s1 is not None
        assert row_s1["p_kw"] == pytest.approx(p_kw)
        assert row_s1["q_kvar"] == pytest.approx(q_kvar)
        assert row_s1["s_kva"] == pytest.approx(s_kva)
        assert row_s1["i_a"] == pytest.approx(i_a)

        row_s2 = con.execute(
            """
            SELECT 1
            FROM section_calc
            WHERE panel_id = ? AND bus_section_id = ? AND mode = ?
            """,
            (parent_panel_id, section_s2_id, "NORMAL"),
        ).fetchone()
        assert row_s2 is None
    finally:
        con.close()


def test_section_aggregation_v2_emergency_mode_loads_in_reserve_section_only(tmp_path: Path) -> None:
    """
    Consumer with MAIN->S1 and RESERVE->S2.
    mode=EMERGENCY => load only in S2; S1 has no row.
    """
    db_path = _make_db_v2(tmp_path)
    parent_panel_id = _uuid()
    child_panel_id = _uuid()
    section_s1_id = _uuid()
    section_s2_id = _uuid()
    consumer_id = _uuid()

    p_kw = 8.0
    q_kvar = 4.0
    s_kva = 8.9
    i_a = 13.0

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
            (section_s1_id, parent_panel_id, "S1"),
        )
        con.execute(
            "INSERT INTO bus_sections (id, panel_id, name) VALUES (?, ?, ?)",
            (section_s2_id, parent_panel_id, "S2"),
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
            INSERT INTO consumer_feeds (id, consumer_id, bus_section_id, feed_role, feed_role_id, priority)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (_uuid(), consumer_id, section_s1_id, "NORMAL", "MAIN", 1),
        )
        con.execute(
            """
            INSERT INTO consumer_feeds (id, consumer_id, bus_section_id, feed_role, feed_role_id, priority)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (_uuid(), consumer_id, section_s2_id, "RESERVE", "RESERVE", 1),
        )
        con.commit()
    finally:
        con.close()

    try:
        from calc_core.section_aggregation import calc_section_loads
    except ImportError as exc:
        pytest.fail(f"Missing calc_core.section_aggregation.calc_section_loads: {exc}")

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        calc_section_loads(con, parent_panel_id, mode="EMERGENCY")

        row_s1 = con.execute(
            """
            SELECT 1
            FROM section_calc
            WHERE panel_id = ? AND bus_section_id = ? AND mode = ?
            """,
            (parent_panel_id, section_s1_id, "EMERGENCY"),
        ).fetchone()
        assert row_s1 is None

        row_s2 = con.execute(
            """
            SELECT p_kw, q_kvar, s_kva, i_a
            FROM section_calc
            WHERE panel_id = ? AND bus_section_id = ? AND mode = ?
            """,
            (parent_panel_id, section_s2_id, "EMERGENCY"),
        ).fetchone()
        assert row_s2 is not None
        assert row_s2["p_kw"] == pytest.approx(p_kw)
        assert row_s2["q_kvar"] == pytest.approx(q_kvar)
        assert row_s2["s_kva"] == pytest.approx(s_kva)
        assert row_s2["i_a"] == pytest.approx(i_a)
    finally:
        con.close()


def test_section_aggregation_v2_both_modes_switches_sections(tmp_path: Path) -> None:
    """
    Call calc_section_loads for NORMAL and EMERGENCY; assert S1 only for NORMAL,
    S2 only for EMERGENCY.
    """
    db_path = _make_db_v2(tmp_path)
    parent_panel_id = _uuid()
    child_panel_id = _uuid()
    section_s1_id = _uuid()
    section_s2_id = _uuid()
    consumer_id = _uuid()

    p_kw = 5.0
    q_kvar = 2.5
    s_kva = 5.6
    i_a = 8.1

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
            (section_s1_id, parent_panel_id, "S1"),
        )
        con.execute(
            "INSERT INTO bus_sections (id, panel_id, name) VALUES (?, ?, ?)",
            (section_s2_id, parent_panel_id, "S2"),
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
            INSERT INTO consumer_feeds (id, consumer_id, bus_section_id, feed_role, feed_role_id, priority)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (_uuid(), consumer_id, section_s1_id, "NORMAL", "MAIN", 1),
        )
        con.execute(
            """
            INSERT INTO consumer_feeds (id, consumer_id, bus_section_id, feed_role, feed_role_id, priority)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (_uuid(), consumer_id, section_s2_id, "RESERVE", "RESERVE", 1),
        )
        con.commit()
    finally:
        con.close()

    try:
        from calc_core.section_aggregation import calc_section_loads
    except ImportError as exc:
        pytest.fail(f"Missing calc_core.section_aggregation.calc_section_loads: {exc}")

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        calc_section_loads(con, parent_panel_id, mode="NORMAL")
        calc_section_loads(con, parent_panel_id, mode="EMERGENCY")

        # NORMAL: only S1
        row_n_s1 = con.execute(
            "SELECT 1 FROM section_calc WHERE panel_id=? AND bus_section_id=? AND mode=?",
            (parent_panel_id, section_s1_id, "NORMAL"),
        ).fetchone()
        row_n_s2 = con.execute(
            "SELECT 1 FROM section_calc WHERE panel_id=? AND bus_section_id=? AND mode=?",
            (parent_panel_id, section_s2_id, "NORMAL"),
        ).fetchone()
        assert row_n_s1 is not None
        assert row_n_s2 is None

        # EMERGENCY: only S2
        row_e_s1 = con.execute(
            "SELECT 1 FROM section_calc WHERE panel_id=? AND bus_section_id=? AND mode=?",
            (parent_panel_id, section_s1_id, "EMERGENCY"),
        ).fetchone()
        row_e_s2 = con.execute(
            "SELECT 1 FROM section_calc WHERE panel_id=? AND bus_section_id=? AND mode=?",
            (parent_panel_id, section_s2_id, "EMERGENCY"),
        ).fetchone()
        assert row_e_s1 is None
        assert row_e_s2 is not None
    finally:
        con.close()
