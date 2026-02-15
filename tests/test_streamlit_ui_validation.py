from __future__ import annotations

import pandas as pd

from app.validation import validate_panel_for_rtm, validate_rtm_rows


def test_validate_rtm_rows_blocks_invalid_values() -> None:
    df = pd.DataFrame(
        [
            {
                "id": None,
                "name": "",
                "n": 0,
                "pn_kw": -1,
                "ki": "nan",
                "cos_phi": 1.5,
                "tg_phi": "x",
                "phases": 2,
                "phase_mode": "BAD",
                "phase_fixed": "Z",
            }
        ]
    )
    res = validate_rtm_rows(df)
    assert res.has_errors
    # High-signal: we should catch at least name/n/pn_kw/ki/phases/phase_mode problems.
    joined = "\n".join(res.errors)
    assert "name is required" in joined
    assert "n must be integer > 0" in joined
    assert "pn_kw must be >= 0" in joined
    assert "ki must be a finite number" in joined
    assert "phases must be 1 or 3" in joined
    assert "phase_mode must be AUTO, FIXED, or NONE" in joined


def test_validate_rtm_rows_fixed_phase_rules() -> None:
    df = pd.DataFrame(
        [
            {
                "id": None,
                "name": "L1",
                "n": 1,
                "pn_kw": 1.0,
                "ki": 0.7,
                "cos_phi": None,
                "tg_phi": None,
                "phases": 1,
                "phase_mode": "FIXED",
                "phase_fixed": "",
            }
        ]
    )
    res = validate_rtm_rows(df)
    assert res.has_errors
    assert "phase_fixed must be A, B, or C when FIXED" in "\n".join(res.errors)


def test_validate_panel_for_rtm_requires_voltage() -> None:
    panel_3ph = {"system_type": "3PH", "u_ll_v": None, "u_ph_v": None}
    errors = validate_panel_for_rtm(panel_3ph)
    assert errors and "u_ll_v must be positive" in errors[0]

    panel_1ph = {"system_type": "1PH", "u_ll_v": 0, "u_ph_v": 0}
    errors = validate_panel_for_rtm(panel_1ph)
    assert errors and "u_ph_v (or u_ll_v) must be positive" in errors[0]

