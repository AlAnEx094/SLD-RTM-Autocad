from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from calc_core.kr_resolver import resolve_kr


ROOT = Path(__file__).resolve().parents[1]


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "t.sqlite"
    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON;")
        con.executescript((ROOT / "db" / "migrations" / "0001_init.sql").read_text(encoding="utf-8"))
        con.executescript((ROOT / "db" / "seed_kr_table.sql").read_text(encoding="utf-8"))
        con.commit()
    finally:
        con.close()
    return db_path


def _kr_from_db(db_path: Path, ne: int, ki: float) -> float:
    con = sqlite3.connect(db_path)
    try:
        row = con.execute(
            "SELECT kr FROM kr_table WHERE ne = ? AND ki = ?",
            (ne, ki),
        ).fetchone()
    finally:
        con.close()
    assert row is not None, f"kr_table must include ne={ne} ki={ki}"
    return float(row[0])


def test_clamp_low_ki_to_010(tmp_path: Path) -> None:
    db_path = _make_db(tmp_path)
    res = resolve_kr(str(db_path), ne=4, ki=0.01)
    assert res.ki_clamped == pytest.approx(0.10)
    assert res.ne_tab == 4
    expected = _kr_from_db(db_path, ne=4, ki=0.10)
    assert res.kr == pytest.approx(expected)


def test_clamp_high_ki_to_080(tmp_path: Path) -> None:
    db_path = _make_db(tmp_path)
    res = resolve_kr(str(db_path), ne=4, ki=0.99)
    assert res.ki_clamped == pytest.approx(0.80)
    assert res.ne_tab == 4
    expected = _kr_from_db(db_path, ne=4, ki=0.80)
    assert res.kr == pytest.approx(expected)


def test_ne_rounds_up_to_next_existing_row(tmp_path: Path) -> None:
    db_path = _make_db(tmp_path)
    # Use an ne not present in the table to force rounding up.
    res = resolve_kr(str(db_path), ne=26, ki=0.80)
    assert res.ne_tab == 30
    expected = _kr_from_db(db_path, ne=30, ki=0.80)
    assert res.kr == pytest.approx(expected)


def test_linear_interpolation_only_by_ki(tmp_path: Path) -> None:
    db_path = _make_db(tmp_path)
    # interpolate strictly between Ki=0.70 and Ki=0.80
    res = resolve_kr(str(db_path), ne=4, ki=0.71)
    assert res.ne_tab == 4
    assert res.ki_clamped == pytest.approx(0.71)
    kr_lo = _kr_from_db(db_path, ne=4, ki=0.70)
    kr_hi = _kr_from_db(db_path, ne=4, ki=0.80)
    expected = kr_lo + ((0.71 - 0.70) / (0.80 - 0.70)) * (kr_hi - kr_lo)
    assert res.kr == pytest.approx(expected)

