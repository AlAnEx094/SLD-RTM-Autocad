"""Feeds v2 migration tests: seed data and backward mapping of v1 feed_role -> feed_role_id."""

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


def _apply_migrations_0001_to_0006(con: sqlite3.Connection) -> None:
    """Apply migrations 0001..0006 sequentially (idempotent)."""
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


def test_feeds_v2_migration_seed_feed_roles_and_modes(tmp_path: Path) -> None:
    """Apply migrations 0001..0006 and assert feed_roles and modes are seeded."""
    db_path = tmp_path / "feeds_v2_migration.sqlite"
    con = sqlite3.connect(db_path)
    try:
        _apply_migrations_0001_to_0006(con)
        con.commit()

        # Assert feed_roles seeded: MAIN, RESERVE, DG, DC, UPS
        feed_role_codes = {
            row[0]
            for row in con.execute("SELECT code FROM feed_roles").fetchall()
        }
        assert feed_role_codes == {"MAIN", "RESERVE", "DG", "DC", "UPS"}

        # Assert modes seeded: NORMAL, EMERGENCY
        mode_codes = {
            row[0]
            for row in con.execute("SELECT code FROM modes").fetchall()
        }
        assert mode_codes == {"NORMAL", "EMERGENCY"}
    finally:
        con.close()


def test_feeds_v2_migration_backward_mapping_v1_feed_role_to_feed_role_id(
    tmp_path: Path,
) -> None:
    """
    Create v1-style consumer_feeds with feed_role NORMAL/RESERVE and NULL feed_role_id,
    run the mapping UPDATE, assert feed_role_id becomes MAIN/RESERVE.
    """
    db_path = tmp_path / "feeds_v2_backward.sqlite"
    con = sqlite3.connect(db_path)
    try:
        _apply_migrations_0001_to_0006(con)
        con.commit()

        # Create minimal data: panel, bus_section, consumer
        panel_id = _uuid()
        section_id = _uuid()
        consumer_id = _uuid()

        con.execute(
            """
            INSERT INTO panels (id, name, system_type, u_ll_v, u_ph_v)
            VALUES (?, ?, ?, ?, ?)
            """,
            (panel_id, "P1", "3PH", 400.0, 230.0),
        )
        con.execute(
            "INSERT INTO bus_sections (id, panel_id, name) VALUES (?, ?, ?)",
            (section_id, panel_id, "S1"),
        )
        con.execute(
            """
            INSERT INTO consumers (id, panel_id, name, load_ref_type, load_ref_id, p_kw, q_kvar, s_kva, i_a)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (consumer_id, panel_id, "C1", "MANUAL", "dummy", 10.0, 5.0, 11.2, 16.0),
        )

        # Insert v1-style consumer_feeds: feed_role NORMAL/RESERVE, feed_role_id NULL
        feed_normal_id = _uuid()
        feed_reserve_id = _uuid()
        section_reserve_id = _uuid()
        con.execute(
            "INSERT INTO bus_sections (id, panel_id, name) VALUES (?, ?, ?)",
            (section_reserve_id, panel_id, "S2"),
        )

        con.execute(
            """
            INSERT INTO consumer_feeds (id, consumer_id, bus_section_id, feed_role, feed_role_id, priority)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (feed_normal_id, consumer_id, section_id, "NORMAL", None, 1),
        )
        con.execute(
            """
            INSERT INTO consumer_feeds (id, consumer_id, bus_section_id, feed_role, feed_role_id, priority)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (feed_reserve_id, consumer_id, section_reserve_id, "RESERVE", None, 1),
        )
        con.commit()

        # Run the backward mapping UPDATE (same logic as migration 0005)
        con.execute(
            """
            UPDATE consumer_feeds
            SET feed_role_id = CASE
              WHEN feed_role = 'NORMAL' THEN 'MAIN'
              WHEN feed_role = 'RESERVE' THEN 'RESERVE'
              ELSE feed_role_id
            END
            WHERE feed_role_id IS NULL AND feed_role IN ('NORMAL', 'RESERVE')
            """
        )
        con.commit()

        # Assert feed_role_id populated: NORMAL -> MAIN, RESERVE -> RESERVE
        row_normal = con.execute(
            "SELECT feed_role_id FROM consumer_feeds WHERE id = ?",
            (feed_normal_id,),
        ).fetchone()
        assert row_normal is not None
        assert row_normal[0] == "MAIN"

        row_reserve = con.execute(
            "SELECT feed_role_id FROM consumer_feeds WHERE id = ?",
            (feed_reserve_id,),
        ).fetchone()
        assert row_reserve is not None
        assert row_reserve[0] == "RESERVE"
    finally:
        con.close()


def test_feeds_v2_migration_idempotent(tmp_path: Path) -> None:
    """Re-run seed statements; reference data should remain consistent."""
    db_path = tmp_path / "feeds_v2_idempotent.sqlite"
    con = sqlite3.connect(db_path)
    try:
        _apply_migrations_0001_to_0006(con)
        con.commit()
        codes_1 = {r[0] for r in con.execute("SELECT code FROM feed_roles").fetchall()}
        assert codes_1 == {"MAIN", "RESERVE", "DG", "DC", "UPS"}

        # Re-run seed statements (do NOT re-run full migrations; SQLite ALTER ADD COLUMN is not idempotent).
        con.execute(
            """
            INSERT INTO feed_roles (id, code, title_ru, title_en, is_default) VALUES
              ('MAIN', 'MAIN', 'Основной', 'Main', 1),
              ('RESERVE', 'RESERVE', 'Резервный', 'Reserve', 0),
              ('DG', 'DG', 'ДГУ', 'DG', 0),
              ('DC', 'DC', 'DC', 'DC', 0),
              ('UPS', 'UPS', 'ИБП', 'UPS', 0)
            ON CONFLICT(code) DO UPDATE SET
              title_ru = excluded.title_ru,
              title_en = excluded.title_en,
              is_default = excluded.is_default
            """
        )
        con.execute(
            """
            INSERT OR IGNORE INTO modes (id, code) VALUES
              ('NORMAL', 'NORMAL'),
              ('EMERGENCY', 'EMERGENCY')
            """
        )
        con.commit()

        codes_2 = {r[0] for r in con.execute("SELECT code FROM feed_roles").fetchall()}
        assert codes_2 == {"MAIN", "RESERVE", "DG", "DC", "UPS"}
        assert int(con.execute("SELECT COUNT(*) FROM feed_roles").fetchone()[0]) == 5
        assert int(con.execute("SELECT COUNT(*) FROM modes").fetchone()[0]) == 2
    finally:
        con.close()
