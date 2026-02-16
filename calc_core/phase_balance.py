"""
Phase balance for 1PH circuits (MVP-BAL v0.1).

Greedy bin-packing assignment of 1Φ circuits to L1/L2/L3 to minimize
current unbalance. Per docs/contracts/PHASE_BALANCE_V0_1.md.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

PHASES_1PH = 1
PHASES_VALID = (1, 3)
MODE_VALID = ("NORMAL", "EMERGENCY")


def calc_phase_balance(
    conn: sqlite3.Connection,
    panel_id: str,
    *,
    mode: str = "NORMAL",
) -> int:
    """
    Assign phases L1/L2/L3 to all 1PH circuits of a panel using greedy bin-packing.
    Writes circuits.phase and upserts panel_phase_balance.

    Returns number of 1PH circuits processed.
    """
    if not panel_id or not isinstance(panel_id, str) or not panel_id.strip():
        raise ValueError("panel_id is required")
    panel_id = panel_id.strip()

    mode_norm = mode.strip().upper()
    if mode_norm not in MODE_VALID:
        raise ValueError(f"mode must be one of {MODE_VALID}")

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    # 1) Select all 1PH circuits with I: prefer circuit_calc.i_calc_a else circuits.i_calc_a
    rows = conn.execute(
        """
        SELECT
          c.id AS circuit_id,
          COALESCE(cc.i_calc_a, c.i_calc_a) AS i_a
        FROM circuits c
        LEFT JOIN circuit_calc cc ON cc.circuit_id = c.id
        WHERE c.panel_id = ? AND c.phases = ?
        """,
        (panel_id, PHASES_1PH),
    ).fetchall()

    if not rows:
        # No 1PH circuits; still upsert panel_phase_balance with zeros
        _upsert_panel_phase_balance(conn, panel_id, mode_norm, 0.0, 0.0, 0.0)
        conn.commit()
        return 0

    # 2) Build list (circuit_id, i_a), validate I >= 0
    circuits_with_i: list[tuple[str, float]] = []
    for r in rows:
        cid = str(r["circuit_id"])
        i_val = r["i_a"]
        if i_val is None:
            raise ValueError(f"i_calc_a is NULL for circuit_id={cid}")
        i_float = float(i_val)
        if i_float < 0:
            raise ValueError(f"I must be >= 0 for circuit_id={cid}, got {i_float}")
        circuits_with_i.append((cid, i_float))

    # 3) Sort by I desc, tie-break by circuit_id (asc for stability)
    circuits_with_i.sort(key=lambda x: (-x[1], x[0]))

    # 4) Greedy assignment: assign each circuit to phase with minimal current sum
    sum_l1 = 0.0
    sum_l2 = 0.0
    sum_l3 = 0.0

    for circuit_id, i_a in circuits_with_i:
        min_sum = min(sum_l1, sum_l2, sum_l3)
        if sum_l1 == min_sum:
            phase = "L1"
            sum_l1 += i_a
        elif sum_l2 == min_sum:
            phase = "L2"
            sum_l2 += i_a
        else:
            phase = "L3"
            sum_l3 += i_a
        conn.execute(
            "UPDATE circuits SET phase = ? WHERE id = ?",
            (phase, circuit_id),
        )

    # 5) Compute unbalance_pct and upsert panel_phase_balance
    _upsert_panel_phase_balance(conn, panel_id, mode_norm, sum_l1, sum_l2, sum_l3)
    conn.commit()
    return len(circuits_with_i)


def _upsert_panel_phase_balance(
    conn: sqlite3.Connection,
    panel_id: str,
    mode: str,
    i_l1: float,
    i_l2: float,
    i_l3: float,
) -> None:
    i_max = max(i_l1, i_l2, i_l3)
    i_avg = (i_l1 + i_l2 + i_l3) / 3.0
    unbalance_pct = 0.0 if i_avg == 0 else (100.0 * (i_max - i_avg) / i_avg)

    updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO panel_phase_balance (
          panel_id, mode, i_l1, i_l2, i_l3, unbalance_pct, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(panel_id, mode) DO UPDATE SET
          i_l1 = excluded.i_l1,
          i_l2 = excluded.i_l2,
          i_l3 = excluded.i_l3,
          unbalance_pct = excluded.unbalance_pct,
          updated_at = excluded.updated_at
        """,
        (panel_id, mode, i_l1, i_l2, i_l3, unbalance_pct, updated_at),
    )
