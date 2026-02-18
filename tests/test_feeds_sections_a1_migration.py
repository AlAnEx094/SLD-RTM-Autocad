from __future__ import annotations

import sqlite3
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _uuid() -> str:
    return str(uuid.uuid4())


def _read_migration(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_a1_migration_empty_db_has_default_section_number_and_roles(tmp_path: Path) -> None:
    from tools.run_calc import ensure_migrations

    db_path = tmp_path / "a1_empty.sqlite"
    ensure_migrations(db_path)

    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON;")
        panel_id = _uuid()
        con.execute(
            """
            INSERT INTO panels (id, name, system_type, u_ll_v, u_ph_v)
            VALUES (?, ?, ?, ?, ?)
            """,
            (panel_id, "P-A1", "3PH", 400.0, 230.0),
        )
        row = con.execute(
            """
            SELECT name, section_no
            FROM bus_sections
            WHERE panel_id = ?
            """,
            (panel_id,),
        ).fetchone()
        assert row is not None
        assert row[0] == "DEFAULT"
        assert int(row[1]) == 1

        codes = {r[0] for r in con.execute("SELECT code FROM feed_roles").fetchall()}
        assert {"MAIN", "RESERVE", "DG", "UPS", "OTHER"} <= codes
    finally:
        con.close()


def test_a1_migration_legacy_db_backfills_section_no_and_feed_priority(tmp_path: Path) -> None:
    from tools.run_calc import ensure_migrations

    db_path = tmp_path / "a1_legacy.sqlite"
    migrations_dir = ROOT / "db" / "migrations"
    pre_a1 = [
        "0001_init.sql",
        "0002_circuits.sql",
        "0003_bus_and_feeds.sql",
        "0004_section_calc.sql",
        "0005_feeds_v2_refs.sql",
        "0006_section_calc_mode_emergency.sql",
        "0007_phase_balance.sql",
        "0008_phase_source.sql",
        "0009_phase_balance_warnings.sql",
        "0010_circuits_bus_section.sql",
    ]

    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON;")
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              version TEXT PRIMARY KEY,
              applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        for name in pre_a1:
            con.executescript(_read_migration(migrations_dir / name))
            con.execute("INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)", (Path(name).stem,))

        panel_id = _uuid()
        consumer_id = _uuid()
        section_id = _uuid()
        feed_id = _uuid()
        con.execute(
            """
            INSERT INTO panels (id, name, system_type, u_ll_v, u_ph_v)
            VALUES (?, ?, ?, ?, ?)
            """,
            (panel_id, "P-LEG", "3PH", 400.0, 230.0),
        )
        con.execute("DELETE FROM bus_sections WHERE panel_id = ?", (panel_id,))
        con.execute(
            "INSERT INTO bus_sections (id, panel_id, name) VALUES (?, ?, ?)",
            (section_id, panel_id, "DEFAULT"),
        )
        con.execute(
            """
            INSERT INTO consumers (id, panel_id, name, load_ref_type, load_ref_id, p_kw, q_kvar, s_kva, i_a)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (consumer_id, panel_id, "C-LEG", "MANUAL", "x", 1.0, 0.5, 1.1, 2.0),
        )
        con.execute(
            """
            INSERT INTO consumer_feeds (id, consumer_id, bus_section_id, feed_role, feed_role_id, priority)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (feed_id, consumer_id, section_id, "NORMAL", None, 7),
        )
        con.commit()
    finally:
        con.close()

    ensure_migrations(db_path)

    con = sqlite3.connect(db_path)
    try:
        sec_no = con.execute(
            "SELECT section_no FROM bus_sections WHERE id = ?",
            (section_id,),
        ).fetchone()
        assert sec_no is not None
        assert int(sec_no[0]) == 1

        feed_prio = con.execute(
            "SELECT priority, feed_priority FROM consumer_feeds WHERE id = ?",
            (feed_id,),
        ).fetchone()
        assert feed_prio is not None
        assert int(feed_prio[0]) == 7
        assert int(feed_prio[1]) == 7

        links_count = int(con.execute("SELECT COUNT(*) FROM bus_section_feeds").fetchone()[0])
        assert links_count >= 1
    finally:
        con.close()
