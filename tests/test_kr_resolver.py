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


def test_clamp_low_ki_to_010(tmp_path: Path) -> None:
    db_path = _make_db(tmp_path)
    res = resolve_kr(str(db_path), ne=4, ki=0.01)
    assert res.ki_clamped == pytest.approx(0.10)
    assert res.ne_tab == 4
    assert res.kr == pytest.approx(1.80)


def test_clamp_high_ki_to_080(tmp_path: Path) -> None:
    db_path = _make_db(tmp_path)
    res = resolve_kr(str(db_path), ne=4, ki=0.99)
    assert res.ki_clamped == pytest.approx(0.80)
    assert res.ne_tab == 4
    assert res.kr == pytest.approx(1.00)


def test_ne_rounds_up_to_next_existing_row(tmp_path: Path) -> None:
    db_path = _make_db(tmp_path)
    # In seed we only have ne=4, so ne=3 must use ne_tab=4.
    res = resolve_kr(str(db_path), ne=3, ki=0.80)
    assert res.ne_tab == 4
    assert res.kr == pytest.approx(1.00)


def test_linear_interpolation_only_by_ki(tmp_path: Path) -> None:
    db_path = _make_db(tmp_path)
    # seed: (0.70 -> 1.20), (0.75 -> 1.10)
    # ki=0.725 is midway => kr=1.15
    res = resolve_kr(str(db_path), ne=4, ki=0.725)
    assert res.ne_tab == 4
    assert res.ki_clamped == pytest.approx(0.725)
    assert res.kr == pytest.approx(1.15)

