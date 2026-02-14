from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class KrResolution:
    ne_input: float
    ki_input: float
    ki_clamped: float
    ne_tab: int
    kr: float

    ki_lo: float | None = None
    ki_hi: float | None = None
    kr_lo: float | None = None
    kr_hi: float | None = None


def _clamp_ki(ki: float) -> float:
    # ЖЁСТКИЙ КОНТРАКТ: clamp Ki в [0.10, 0.80]
    if ki < 0.10:
        return 0.10
    if ki > 0.80:
        return 0.80
    return ki


def _iter_row_points(con: sqlite3.Connection, ne_tab: int) -> list[tuple[float, float]]:
    rows = con.execute(
        "SELECT ki, kr FROM kr_table WHERE ne = ? ORDER BY ki ASC",
        (ne_tab,),
    ).fetchall()
    return [(float(ki), float(kr)) for (ki, kr) in rows]


def resolve_kr(db_path: str, ne: float, ki: float, *, eps: float = 1e-12) -> KrResolution:
    """
    Resolve Kr строго по контракту (см. docs/contracts/KR_RESOLVER.md).

    Правила:
    - clamp Ki в [0.10, 0.80]
    - ne_tab = минимальное табличное ne, которое >= ne
    - интерполяция ТОЛЬКО по Ki внутри ne_tab (линейная)
    - при точном попадании в столбец -> табличное значение
    - ошибка при отсутствии ne_tab или невозможности интерполяции
    """
    if not isinstance(ne, (int, float)) or isinstance(ne, bool):
        raise TypeError("ne must be a number")
    ne_val = float(ne)
    if math.isnan(ne_val) or math.isinf(ne_val):
        raise ValueError("ne must be finite")
    if ne_val <= 0:
        raise ValueError("ne must be positive")
    if not isinstance(ki, (int, float)):
        raise TypeError("ki must be a number")
    if math.isnan(float(ki)) or math.isinf(float(ki)):
        raise ValueError("ki must be finite")

    ki_in = float(ki)
    ki_clamped = float(_clamp_ki(ki_in))

    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON;")

        # 1) ne_tab = MIN(ne) WHERE ne >= ne_input
        row = con.execute(
            "SELECT MIN(ne) FROM kr_table WHERE ne >= ?",
            (ne_val,),
        ).fetchone()
        ne_tab = row[0] if row else None
        if ne_tab is None:
            raise ValueError(f"No ne_tab found in kr_table for ne={ne}")
        ne_tab = int(ne_tab)

        pts = _iter_row_points(con, ne_tab)
        if not pts:
            raise ValueError(f"No kr_table data for ne_tab={ne_tab}")

        # 2) exact-match with tolerance (REAL in SQLite is float-like)
        for ki_col, kr_val in pts:
            if abs(ki_col - ki_clamped) <= eps:
                return KrResolution(
                    ne_input=ne_val,
                    ki_input=ki_in,
                    ki_clamped=ki_clamped,
                    ne_tab=ne_tab,
                    kr=kr_val,
                )

        # 3) find neighbors for interpolation
        ki_lo = None
        kr_lo = None
        for ki_col, kr_val in pts:
            if ki_col < ki_clamped:
                ki_lo = ki_col
                kr_lo = kr_val
            else:
                break

        ki_hi = None
        kr_hi = None
        for ki_col, kr_val in pts:
            if ki_col > ki_clamped:
                ki_hi = ki_col
                kr_hi = kr_val
                break

        if ki_lo is None or ki_hi is None or kr_lo is None or kr_hi is None:
            raise ValueError(
                "Cannot interpolate Kr for "
                f"ne_tab={ne_tab}, ki_clamped={ki_clamped}; "
                "kr_table row does not contain bounding Ki columns"
            )

        # 4) linear interpolation by Ki
        kr = kr_lo + ((ki_clamped - ki_lo) / (ki_hi - ki_lo)) * (kr_hi - kr_lo)
        return KrResolution(
            ne_input=ne_val,
            ki_input=ki_in,
            ki_clamped=ki_clamped,
            ne_tab=ne_tab,
            kr=float(kr),
            ki_lo=ki_lo,
            ki_hi=ki_hi,
            kr_lo=kr_lo,
            kr_hi=kr_hi,
        )
    finally:
        con.close()


def get_kr(db_path: str, ne: float, ki: float) -> float:
    """Возвращает только Kr (обёртка над resolve_kr)."""
    return resolve_kr(db_path, ne, ki).kr

