from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ValidationResult:
    errors: list[str]
    warnings: list[str]
    row_status: dict[int, str]

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


def is_finite(value: Any) -> bool:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(num)


def validate_panel(data: dict[str, Any]) -> list[str]:
    """
    Strict-ish panel validation for operator UI (no formulas).
    """
    errors: list[str] = []
    name = str(data.get("name") or "").strip()
    if not name:
        errors.append("name is required")

    system_type = data.get("system_type")
    if system_type not in ("3PH", "1PH"):
        errors.append("system_type must be 3PH or 1PH")

    for field in ("du_limit_lighting_pct", "du_limit_other_pct"):
        val = data.get(field)
        if val is None:
            errors.append(f"{field} is required")
        else:
            try:
                if float(val) < 0:
                    errors.append(f"{field} must be >= 0")
            except (TypeError, ValueError):
                errors.append(f"{field} must be a number")

    for field in ("u_ll_v", "u_ph_v"):
        val = data.get(field)
        if val is None or val == "":
            continue
        try:
            if float(val) <= 0:
                errors.append(f"{field} must be > 0 when provided")
        except (TypeError, ValueError):
            errors.append(f"{field} must be a number")

    return errors


def validate_panel_for_rtm(panel: dict[str, Any]) -> list[str]:
    """
    Validation needed to allow RTM calculation, matching calc_core requirements.
    """
    errors: list[str] = []
    system_type = str(panel.get("system_type") or "").strip().upper()
    u_ll_v = panel.get("u_ll_v")
    u_ph_v = panel.get("u_ph_v")

    def _pos(v: Any) -> bool:
        return v is not None and is_finite(v) and float(v) > 0

    if system_type == "3PH":
        if not _pos(u_ll_v):
            errors.append("u_ll_v must be positive for 3PH RTM calculation")
    elif system_type == "1PH":
        if not (_pos(u_ph_v) or _pos(u_ll_v)):
            errors.append("u_ph_v (or u_ll_v) must be positive for 1PH RTM calculation")
    else:
        errors.append("system_type must be 3PH or 1PH")

    return errors


def validate_rtm_rows(df: pd.DataFrame) -> ValidationResult:
    """
    Validates RTM input rows (rtm_rows) as shown in the unified Load Table.

    Expects DataFrame with columns:
    id, name, n, pn_kw, ki, cos_phi, tg_phi, phases, phase_mode, phase_fixed
    """
    errors: list[str] = []
    warnings: list[str] = []
    statuses: dict[int, str] = {}

    for idx, row in df.iterrows():
        row_errors: list[str] = []
        row_warnings: list[str] = []

        name = str(row.get("name") or "").strip()
        label = name or str(row.get("id") or f"row#{idx}")

        n_val = row.get("n")
        if n_val is None or n_val == "" or pd.isna(n_val):
            row_errors.append("n is required")
        else:
            try:
                n_float = float(n_val)
                if not n_float.is_integer() or int(n_float) <= 0:
                    row_errors.append("n must be integer > 0")
            except (TypeError, ValueError):
                row_errors.append("n must be integer > 0")

        pn_kw = row.get("pn_kw")
        if pn_kw is None or pn_kw == "" or pd.isna(pn_kw):
            row_errors.append("pn_kw is required")
        elif not is_finite(pn_kw) or float(pn_kw) < 0:
            row_errors.append("pn_kw must be >= 0")

        ki = row.get("ki")
        if ki is None or ki == "" or pd.isna(ki):
            row_errors.append("ki is required")
        elif not is_finite(ki):
            row_errors.append("ki must be a finite number")
        else:
            ki_val = float(ki)
            if ki_val < 0.10 or ki_val > 0.80:
                row_warnings.append("ki will be clamped to [0.10..0.80]")

        cos_phi = row.get("cos_phi")
        if cos_phi not in (None, "") and not pd.isna(cos_phi):
            if not is_finite(cos_phi):
                row_errors.append("cos_phi must be finite")
            else:
                cos_val = float(cos_phi)
                if cos_val <= 0 or cos_val > 1:
                    row_errors.append("cos_phi must be in (0, 1]")

        tg_phi = row.get("tg_phi")
        if tg_phi not in (None, "") and not pd.isna(tg_phi) and not is_finite(tg_phi):
            row_errors.append("tg_phi must be finite")

        phases = row.get("phases")
        if phases is None or phases == "" or pd.isna(phases):
            row_errors.append("phases is required")
        else:
            try:
                phases_int = int(float(phases))
                if phases_int not in (1, 3):
                    row_errors.append("phases must be 1 or 3")
            except (TypeError, ValueError):
                row_errors.append("phases must be 1 or 3")

        phase_mode = str(row.get("phase_mode") or "").strip().upper()
        if phase_mode not in ("AUTO", "FIXED", "NONE"):
            row_errors.append("phase_mode must be AUTO, FIXED, or NONE")

        phase_fixed = str(row.get("phase_fixed") or "").strip().upper()
        if phase_mode == "FIXED":
            if phase_fixed not in ("A", "B", "C"):
                row_errors.append("phase_fixed must be A, B, or C when FIXED")
        else:
            if phase_fixed:
                row_errors.append("phase_fixed must be empty unless FIXED")

        if not name:
            row_errors.append("name is required")

        if row_errors:
            errors.append(f"{label}: " + "; ".join(row_errors))
            statuses[idx] = "INVALID"
        else:
            statuses[idx] = "OK"

        if row_warnings:
            warnings.append(f"{label}: " + "; ".join(row_warnings))

    return ValidationResult(errors=errors, warnings=warnings, row_status=statuses)

