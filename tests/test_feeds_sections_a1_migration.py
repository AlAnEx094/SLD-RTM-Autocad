from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run_sql(conn: sqlite3.Connection, name: str) -> None:
    path = ROOT / "db" / "migrations" / name
    conn.executescript(path.read_text(encoding="utf-8"))


def test_a1_migration_on_empty_db(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        from tools.run_calc import ensure_migrations

        ensure_migrations(db_path)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(bus_sections)").fetchall()}
        assert "section_no" in cols
        assert "section_label" in cols

        cf_cols = {r[1] for r in conn.execute("PRAGMA table_info(consumer_feeds)").fetchall()}
        assert "feed_priority" in cf_cols

        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "feeds" in tables
        assert "bus_section_feeds" in tables
    finally:
        conn.close()


def test_a1_migration_on_legacy_db_default_section_no(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        _run_sql(conn, "0001_init.sql")
        _run_sql(conn, "0002_circuits.sql")
        _run_sql(conn, "0003_bus_and_feeds.sql")
        _run_sql(conn, "0004_section_calc.sql")

        panel_id = "p-1"
        conn.execute(
            "INSERT INTO panels (id, name, system_type, u_ll_v, u_ph_v) VALUES (?, ?, ?, ?, ?)",
            (panel_id, "P1", "3PH", 400.0, 230.0),
        )
        conn.execute(
            "INSERT INTO bus_sections (id, panel_id, name) VALUES (?, ?, ?)",
            ("bs-default", panel_id, "DEFAULT"),
        )
        conn.commit()

        _run_sql(conn, "0005_feeds_v2_refs.sql")
        _run_sql(conn, "0006_section_calc_mode_emergency.sql")
        _run_sql(conn, "0007_phase_balance.sql")
        _run_sql(conn, "0008_phase_source.sql")
        _run_sql(conn, "0009_phase_balance_warnings.sql")
        _run_sql(conn, "0010_circuits_bus_section.sql")
        _run_sql(conn, "0011_feeds_sections_a1.sql")
        conn.commit()

        section_no = conn.execute(
            "SELECT section_no FROM bus_sections WHERE id = ?",
            ("bs-default",),
        ).fetchone()[0]
        assert section_no == 1
    finally:
        conn.close()


def test_a1_feed_roles_include_dg_ups_other(tmp_path: Path) -> None:
    db_path = tmp_path / "roles.sqlite"
    from tools.run_calc import ensure_migrations

    ensure_migrations(db_path)
    conn = sqlite3.connect(db_path)
    try:
        codes = {r[0] for r in conn.execute("SELECT code FROM feed_roles").fetchall()}
        assert {"DG", "UPS", "OTHER"}.issubset(codes)
    finally:
        conn.close()
