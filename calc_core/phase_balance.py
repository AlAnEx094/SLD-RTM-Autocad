"""
Phase balance for 1PH circuits (MVP-BAL v0.1).

Greedy bin-packing assignment of 1Φ circuits to L1/L2/L3 to minimize
current unbalance. Per docs/contracts/PHASE_BALANCE_V0_1.md.
"""

from __future__ import annotations

import json
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
    respect_manual: bool = True,
) -> int:
    """
    Assign phases L1/L2/L3 to all 1PH circuits of a panel using greedy bin-packing.
    Writes circuits.phase and upserts panel_phase_balance.

    When respect_manual=True: circuits with phase_source='MANUAL' are excluded from
    reassignment; their existing phase is preserved and contributes to initial sums
    only when phase is valid (L1/L2/L3). Invalid MANUAL phases are excluded from sums
    and persisted as warnings.
    When respect_manual=False: algorithm may overwrite any phase.

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

    # Check if phase_source column exists (migration 0008)
    circuits_cols = [r[1] for r in conn.execute("PRAGMA table_info(circuits)").fetchall()]
    has_phase_source = "phase_source" in circuits_cols

    # 1) Select all 1PH circuits with I, phase, and optionally phase_source
    if not has_phase_source:
        rows = conn.execute(
            """
            SELECT
              c.id AS circuit_id,
              c.name AS circuit_name,
              COALESCE(cc.i_calc_a, c.i_calc_a) AS i_a,
              NULL AS phase,
              NULL AS phase_source
            FROM circuits c
            LEFT JOIN circuit_calc cc ON cc.circuit_id = c.id
            WHERE c.panel_id = ? AND c.phases = ?
            """,
            (panel_id, PHASES_1PH),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT
              c.id AS circuit_id,
              c.name AS circuit_name,
              COALESCE(cc.i_calc_a, c.i_calc_a) AS i_a,
              c.phase,
              c.phase_source
            FROM circuits c
            LEFT JOIN circuit_calc cc ON cc.circuit_id = c.id
            WHERE c.panel_id = ? AND c.phases = ?
            """,
            (panel_id, PHASES_1PH),
        ).fetchall()

    if not rows:
        # No 1PH circuits; still upsert panel_phase_balance with zeros.
        # Explicitly clear warnings (G1): invalid_manual_count=0, warnings_json=NULL.
        _upsert_panel_phase_balance(
            conn,
            panel_id,
            mode_norm,
            0.0,
            0.0,
            0.0,
            invalid_manual_count=0,
            warnings_json=None,
        )
        conn.commit()
        return 0

    # 2) Split into manual (excluded from reassignment) and auto (reassignable)
    sum_l1 = 0.0
    sum_l2 = 0.0
    sum_l3 = 0.0
    auto_circuits: list[tuple[str, float]] = []
    invalid_manual_count = 0
    warnings: list[dict[str, object]] = []

    for r in rows:
        cid = str(r["circuit_id"])
        cname = r["circuit_name"]
        i_val = r["i_a"]
        if i_val is None:
            raise ValueError(f"i_calc_a is NULL for circuit_id={cid}")
        i_float = float(i_val)
        if i_float < 0:
            raise ValueError(f"I must be >= 0 for circuit_id={cid}, got {i_float}")

        # NOTE: sqlite3.Row does not support .get(); use [] access.
        phase_raw = r["phase"]
        phase_source_val = str(r["phase_source"]).strip() if has_phase_source else "AUTO"

        is_manual = respect_manual and has_phase_source and phase_source_val == "MANUAL"
        phase_val: str | None = None
        if phase_raw is not None:
            s = str(phase_raw).strip()
            if s in ("L1", "L2", "L3"):
                phase_val = s

        if is_manual:
            # Preserve existing phase; add to sums if valid
            if phase_val is not None:
                if phase_val == "L1":
                    sum_l1 += i_float
                elif phase_val == "L2":
                    sum_l2 += i_float
                else:
                    sum_l3 += i_float
            else:
                invalid_manual_count += 1
                warnings.append(
                    {
                        "circuit_id": cid,
                        "name": str(cname) if cname is not None else None,
                        "i_a": i_float,
                        "phase": None if phase_raw is None else str(phase_raw),
                        "phase_source": phase_source_val,
                        "reason": "MANUAL_INVALID_PHASE",
                    }
                )
        else:
            auto_circuits.append((cid, i_float))

    # 3) Sort auto circuits by I desc, tie-break by circuit_id (asc for stability)
    auto_circuits.sort(key=lambda x: (-x[1], x[0]))

    # 4) Greedy assignment: assign each auto circuit to phase with minimal current sum
    for circuit_id, i_a in auto_circuits:
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
    warnings_json: str | None = None
    if warnings:
        warnings.sort(key=lambda w: str(w.get("circuit_id") or ""))
        warnings_json = json.dumps(warnings, ensure_ascii=False)

    _upsert_panel_phase_balance(
        conn,
        panel_id,
        mode_norm,
        sum_l1,
        sum_l2,
        sum_l3,
        invalid_manual_count=invalid_manual_count,
        warnings_json=warnings_json,
    )
    conn.commit()
    return len(rows)


def _upsert_panel_phase_balance(
    conn: sqlite3.Connection,
    panel_id: str,
    mode: str,
    i_l1: float,
    i_l2: float,
    i_l3: float,
    *,
    invalid_manual_count: int = 0,
    warnings_json: str | None = None,
) -> None:
    i_max = max(i_l1, i_l2, i_l3)
    i_avg = (i_l1 + i_l2 + i_l3) / 3.0
    unbalance_pct = 0.0 if i_avg == 0 else (100.0 * (i_max - i_avg) / i_avg)

    updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    pb_cols = [r[1] for r in conn.execute("PRAGMA table_info(panel_phase_balance)").fetchall()]
    has_invalid_manual_count = "invalid_manual_count" in pb_cols
    has_warnings_json = "warnings_json" in pb_cols

    if has_invalid_manual_count and has_warnings_json:
        conn.execute(
            """
            INSERT INTO panel_phase_balance (
              panel_id, mode, i_l1, i_l2, i_l3, unbalance_pct, updated_at,
              invalid_manual_count, warnings_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(panel_id, mode) DO UPDATE SET
              i_l1 = excluded.i_l1,
              i_l2 = excluded.i_l2,
              i_l3 = excluded.i_l3,
              unbalance_pct = excluded.unbalance_pct,
              updated_at = excluded.updated_at,
              invalid_manual_count = excluded.invalid_manual_count,
              warnings_json = excluded.warnings_json
            """,
            (
                panel_id,
                mode,
                i_l1,
                i_l2,
                i_l3,
                unbalance_pct,
                updated_at,
                int(invalid_manual_count),
                warnings_json,
            ),
        )
        return

    # Backward-compatible upsert (older DBs)
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
