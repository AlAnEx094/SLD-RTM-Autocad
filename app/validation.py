from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

Translator = Callable[..., str]

# Default English strings for backward compatibility when translator is not provided.
_VALIDATION_EN = {
    "validation.name_required": "name is required",
    "validation.system_type": "system_type must be 3PH or 1PH",
    "validation.field_required": "{field} is required",
    "validation.field_gte_zero": "{field} must be >= 0",
    "validation.field_number": "{field} must be a number",
    "validation.field_positive_when_provided": "{field} must be > 0 when provided",
    "validation.u_ll_positive_3ph": "u_ll_v must be positive for 3PH RTM calculation",
    "validation.u_ph_positive_1ph": "u_ph_v (or u_ll_v) must be positive for 1PH RTM calculation",
    "validation.n_required": "n is required",
    "validation.n_integer": "n must be integer > 0",
    "validation.pn_kw_required": "pn_kw is required",
    "validation.pn_kw_gte_zero": "pn_kw must be >= 0",
    "validation.ki_required": "ki is required",
    "validation.ki_finite": "ki must be a finite number",
    "validation.ki_clamped": "ki will be clamped to [0.10..0.80]",
    "validation.cos_phi_finite": "cos_phi must be finite",
    "validation.cos_phi_range": "cos_phi must be in (0, 1]",
    "validation.tg_phi_finite": "tg_phi must be finite",
    "validation.phases_required": "phases is required",
    "validation.phases_one_three": "phases must be 1 or 3",
    "validation.phase_mode": "phase_mode must be AUTO, FIXED, or NONE",
    "validation.phase_fixed_abc": "phase_fixed must be A, B, or C when FIXED",
    "validation.phase_fixed_empty": "phase_fixed must be empty unless FIXED",
}


def _tr(translator: Translator | None, key: str, **kwargs: Any) -> str:
    if translator is None:
        raw = _VALIDATION_EN.get(key, key)
        return raw.format(**kwargs) if kwargs else raw
    return translator(key, **kwargs)


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


def validate_panel(data: dict[str, Any], *, translator: Translator | None = None) -> list[str]:
    """
    Strict-ish panel validation for operator UI (no formulas).
    """
    errors: list[str] = []
    name = str(data.get("name") or "").strip()
    if not name:
        errors.append(_tr(translator, "validation.name_required"))

    system_type = data.get("system_type")
    if system_type not in ("3PH", "1PH"):
        errors.append(_tr(translator, "validation.system_type"))

    for field in ("du_limit_lighting_pct", "du_limit_other_pct"):
        val = data.get(field)
        if val is None:
            errors.append(_tr(translator, "validation.field_required", field=field))
        else:
            try:
                if float(val) < 0:
                    errors.append(_tr(translator, "validation.field_gte_zero", field=field))
            except (TypeError, ValueError):
                errors.append(_tr(translator, "validation.field_number", field=field))

    for field in ("u_ll_v", "u_ph_v"):
        val = data.get(field)
        if val is None or val == "":
            continue
        try:
            if float(val) <= 0:
                errors.append(_tr(translator, "validation.field_positive_when_provided", field=field))
        except (TypeError, ValueError):
            errors.append(_tr(translator, "validation.field_number", field=field))

    return errors


def validate_panel_for_rtm(panel: dict[str, Any], *, translator: Translator | None = None) -> list[str]:
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
            errors.append(_tr(translator, "validation.u_ll_positive_3ph"))
    elif system_type == "1PH":
        if not (_pos(u_ph_v) or _pos(u_ll_v)):
            errors.append(_tr(translator, "validation.u_ph_positive_1ph"))
    else:
        errors.append(_tr(translator, "validation.system_type"))

    return errors


def validate_rtm_rows(df: pd.DataFrame, *, translator: Translator | None = None) -> ValidationResult:
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
            row_errors.append(_tr(translator, "validation.n_required"))
        else:
            try:
                n_float = float(n_val)
                if not n_float.is_integer() or int(n_float) <= 0:
                    row_errors.append(_tr(translator, "validation.n_integer"))
            except (TypeError, ValueError):
                row_errors.append(_tr(translator, "validation.n_integer"))

        pn_kw = row.get("pn_kw")
        if pn_kw is None or pn_kw == "" or pd.isna(pn_kw):
            row_errors.append(_tr(translator, "validation.pn_kw_required"))
        elif not is_finite(pn_kw) or float(pn_kw) < 0:
            row_errors.append(_tr(translator, "validation.pn_kw_gte_zero"))

        ki = row.get("ki")
        if ki is None or ki == "" or pd.isna(ki):
            row_errors.append(_tr(translator, "validation.ki_required"))
        elif not is_finite(ki):
            row_errors.append(_tr(translator, "validation.ki_finite"))
        else:
            ki_val = float(ki)
            if ki_val < 0.10 or ki_val > 0.80:
                row_warnings.append(_tr(translator, "validation.ki_clamped"))

        cos_phi = row.get("cos_phi")
        if cos_phi not in (None, "") and not pd.isna(cos_phi):
            if not is_finite(cos_phi):
                row_errors.append(_tr(translator, "validation.cos_phi_finite"))
            else:
                cos_val = float(cos_phi)
                if cos_val <= 0 or cos_val > 1:
                    row_errors.append(_tr(translator, "validation.cos_phi_range"))

        tg_phi = row.get("tg_phi")
        if tg_phi not in (None, "") and not pd.isna(tg_phi) and not is_finite(tg_phi):
            row_errors.append(_tr(translator, "validation.tg_phi_finite"))

        phases = row.get("phases")
        if phases is None or phases == "" or pd.isna(phases):
            row_errors.append(_tr(translator, "validation.phases_required"))
        else:
            try:
                phases_int = int(float(phases))
                if phases_int not in (1, 3):
                    row_errors.append(_tr(translator, "validation.phases_one_three"))
            except (TypeError, ValueError):
                row_errors.append(_tr(translator, "validation.phases_one_three"))

        phase_mode = str(row.get("phase_mode") or "").strip().upper()
        if phase_mode not in ("AUTO", "FIXED", "NONE"):
            row_errors.append(_tr(translator, "validation.phase_mode"))

        phase_fixed = str(row.get("phase_fixed") or "").strip().upper()
        if phase_mode == "FIXED":
            if phase_fixed not in ("A", "B", "C"):
                row_errors.append(_tr(translator, "validation.phase_fixed_abc"))
        else:
            if phase_fixed:
                row_errors.append(_tr(translator, "validation.phase_fixed_empty"))

        if not name:
            row_errors.append(_tr(translator, "validation.name_required"))

        if row_errors:
            errors.append(f"{label}: " + "; ".join(row_errors))
            statuses[idx] = "INVALID"
        else:
            statuses[idx] = "OK"

        if row_warnings:
            warnings.append(f"{label}: " + "; ".join(row_warnings))

    return ValidationResult(errors=errors, warnings=warnings, row_status=statuses)

