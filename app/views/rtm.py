from __future__ import annotations

import math
import sqlite3
from typing import Any

import pandas as pd
import streamlit as st

from app import db


INPUT_COLUMNS = [
    "id",
    "name",
    "n",
    "pn_kw",
    "ki",
    "cos_phi",
    "tg_phi",
    "phases",
    "phase_mode",
    "phase_fixed",
]

CALC_COLUMNS = ["pn_total", "ki_pn", "ki_pn_tg", "n_pn2"]


def _is_finite(value: Any) -> bool:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(num)


def _validate_rows(df: pd.DataFrame) -> tuple[list[str], list[str], dict[int, str]]:
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
        elif not _is_finite(pn_kw) or float(pn_kw) < 0:
            row_errors.append("pn_kw must be >= 0")

        ki = row.get("ki")
        if ki is None or ki == "" or pd.isna(ki):
            row_errors.append("ki is required")
        elif not _is_finite(ki):
            row_errors.append("ki must be a finite number")
        else:
            ki_val = float(ki)
            if ki_val < 0.10 or ki_val > 0.80:
                row_warnings.append("ki will be clamped to [0.10..0.80]")

        cos_phi = row.get("cos_phi")
        if cos_phi not in (None, "") and not pd.isna(cos_phi):
            if not _is_finite(cos_phi):
                row_errors.append("cos_phi must be finite")
            else:
                cos_val = float(cos_phi)
                if cos_val <= 0 or cos_val > 1:
                    row_errors.append("cos_phi must be in (0, 1]")

        tg_phi = row.get("tg_phi")
        if tg_phi not in (None, "") and not pd.isna(tg_phi) and not _is_finite(tg_phi):
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

    return errors, warnings, statuses


def _render_status(label: str, info: db.StatusInfo) -> None:
    if info.status == "OK":
        st.success(f"{label}: OK")
    elif info.status == "STALE":
        st.warning(f"{label}: STALE")
    elif info.status == "NO_CALC":
        st.error(f"{label}: NO_CALC")
    elif info.status == "UNKNOWN":
        st.warning(f"{label}: UNKNOWN")
    elif info.status == "HIDDEN":
        return
    else:
        st.info(f"{label}: {info.status}")
    if info.calc_updated_at:
        st.caption(f"{label} updated_at: {info.calc_updated_at}")


def render(conn, state: dict) -> None:
    st.header("RTM - Load Table")

    panel_id = state.get("selected_panel_id")
    if not panel_id:
        st.info("Select a panel to edit RTM rows.")
        return

    panel = db.get_panel(conn, panel_id)
    if not panel:
        st.warning("Selected panel not found.")
        return

    rtm_info = db.rtm_status(conn, panel_id, external_change=state.get("external_change", False))
    phase_info = db.phase_status(
        conn,
        panel_id,
        system_type=panel.get("system_type"),
        external_change=state.get("external_change", False),
    )
    _render_status("RTM", rtm_info)
    if panel.get("system_type") == "1PH":
        _render_status("PHASE", phase_info)

    rows = db.list_rtm_rows_with_calc(conn, panel_id)
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=INPUT_COLUMNS + CALC_COLUMNS)

    search = st.text_input("Search by name")
    phase_filter = st.multiselect("Phases", [1, 3], default=[1, 3])
    mode_filter = st.multiselect("Phase mode", ["AUTO", "FIXED", "NONE"], default=["AUTO", "FIXED", "NONE"])

    display_df = df.copy()
    if "phase_mode" in display_df.columns:
        display_df["phase_mode"] = display_df["phase_mode"].where(
            display_df["phase_mode"].notna(), ""
        )
        display_df["phase_mode"] = (
            display_df["phase_mode"].astype(str).str.upper().replace({"NAN": ""})
        )
    if "phase_fixed" in display_df.columns:
        display_df["phase_fixed"] = display_df["phase_fixed"].where(
            display_df["phase_fixed"].notna(), ""
        )
        display_df["phase_fixed"] = (
            display_df["phase_fixed"].astype(str).str.upper().replace({"NAN": "", "NONE": ""})
        )

    if search:
        display_df = display_df[
            display_df["name"].astype(str).str.contains(search, case=False, na=False)
        ]
    if phase_filter:
        display_df = display_df[display_df["phases"].isin(phase_filter)]
    if mode_filter:
        display_df = display_df[display_df["phase_mode"].isin(mode_filter)]

    errors, warnings, statuses = _validate_rows(display_df[INPUT_COLUMNS].copy())
    display_df["row_status"] = display_df.index.map(lambda i: statuses.get(i, "OK"))

    st.caption("Edit RTM rows. Calc columns are read-only.")
    edited_df = st.data_editor(
        display_df[INPUT_COLUMNS + CALC_COLUMNS + ["row_status"]],
        num_rows="dynamic",
        disabled=CALC_COLUMNS + ["row_status", "id"],
        use_container_width=True,
        key="rtm_editor",
    )

    input_df = edited_df[INPUT_COLUMNS].copy()
    errors, warnings, _ = _validate_rows(input_df)

    if warnings:
        st.warning("Warnings:\n" + "\n".join(warnings))
    if errors:
        st.error("Validation errors:\n" + "\n".join(errors))

    display_ids = {
        str(rid)
        for rid in display_df["id"].dropna().astype(str).tolist()
        if str(rid).strip()
    }
    edited_ids = {
        str(rid)
        for rid in input_df["id"].dropna().astype(str).tolist()
        if str(rid).strip()
    }
    deleted_ids = sorted(display_ids - edited_ids)

    if deleted_ids:
        st.warning(
            "Rows removed in the table will not be deleted. Use the delete section below."
        )

    can_save = not errors and state.get("mode_effective") == "EDIT"
    if st.button("Save input changes", disabled=not can_save):
        if deleted_ids:
            st.error("Delete rows using the delete section.")
        else:
            try:
                rows_to_save = []
                for _, row in input_df.iterrows():
                    row_id = row.get("id")
                    if row_id in ("", None) or pd.isna(row_id):
                        row_id = None
                    cos_phi = row.get("cos_phi")
                    tg_phi = row.get("tg_phi")
                    rows_to_save.append(
                        {
                            "id": row_id,
                            "name": str(row.get("name") or "").strip(),
                            "n": int(float(row.get("n"))),
                            "pn_kw": float(row.get("pn_kw")),
                            "ki": float(row.get("ki")),
                            "cos_phi": None if cos_phi in (None, "") or pd.isna(cos_phi) else float(cos_phi),
                            "tg_phi": None if tg_phi in (None, "") or pd.isna(tg_phi) else float(tg_phi),
                            "phases": int(float(row.get("phases"))),
                            "phase_mode": str(row.get("phase_mode") or "").strip().upper(),
                            "phase_fixed": str(row.get("phase_fixed") or "").strip().upper() or None,
                        }
                    )

                with db.tx(conn):
                    db.upsert_rtm_rows(conn, panel_id, rows_to_save)
                    db.touch_ui_input_meta(
                        conn, panel_id, db.SUBSYSTEM_RTM, note="rtm_rows_edit"
                    )
                    db.touch_ui_input_meta(
                        conn, panel_id, db.SUBSYSTEM_PHASE, note="rtm_rows_edit"
                    )
                db.update_state_after_write(state, state["db_path"], conn)
                st.success("RTM rows saved.")
            except Exception as exc:  # pragma: no cover - UI error path
                st.error(f"Failed to save RTM rows: {exc}")

    st.subheader("Input totals (from input values)")
    if input_df.empty:
        st.info("No input rows.")
    else:
        pn_total = (input_df["n"].astype(float) * input_df["pn_kw"].astype(float)).sum()
        ki_pn = (input_df["ki"].astype(float) * input_df["n"].astype(float) * input_df["pn_kw"].astype(float)).sum()
        cols = st.columns(2)
        cols[0].metric("Sum pn_total", f"{pn_total:.3f}")
        cols[1].metric("Sum ki_pn", f"{ki_pn:.3f}")

    st.subheader("RTM panel calc (read-only)")
    panel_calc = db.get_rtm_panel_calc(conn, panel_id)
    if panel_calc:
        st.dataframe(panel_calc, use_container_width=True)
    else:
        st.info("rtm_panel_calc is empty.")

    if panel.get("system_type") == "1PH":
        st.subheader("Phase balance (read-only)")
        phase_calc = db.get_panel_phase_calc(conn, panel_id)
        if phase_calc:
            st.dataframe(phase_calc, use_container_width=True)
        else:
            st.info("panel_phase_calc is empty.")

    st.subheader("Recalculate RTM")
    u_ll_v = panel.get("u_ll_v")
    u_ph_v = panel.get("u_ph_v")
    voltage_ok = True
    if panel.get("system_type") == "3PH":
        voltage_ok = u_ll_v is not None and float(u_ll_v) > 0
    else:
        voltage_ok = (u_ph_v is not None and float(u_ph_v) > 0) or (
            u_ll_v is not None and float(u_ll_v) > 0
        )

    can_recalc = (
        state.get("mode_effective") == "EDIT"
        and not errors
        and len(input_df) > 0
        and voltage_ok
    )
    if not voltage_ok:
        st.error("Panel voltage is missing/invalid for RTM calculation.")

    if st.button("Recalculate RTM", disabled=not can_recalc):
        try:
            from calc_core import run_panel_calc

            run_panel_calc(state["db_path"], panel_id, note="streamlit")

            if panel.get("system_type") == "1PH":
                try:
                    from calc_core import phase_balance  # type: ignore

                    ph_conn = sqlite3.connect(state["db_path"])
                    try:
                        ph_conn.row_factory = sqlite3.Row
                        ph_conn.execute("PRAGMA foreign_keys = ON;")
                        phase_balance.balance_panel(ph_conn, panel_id)
                        ph_conn.commit()
                    finally:
                        ph_conn.close()
                except Exception as exc:
                    st.warning(f"Phase balance skipped: {exc}")

            db.update_state_after_write(state, state["db_path"])
            st.success("RTM recalculated.")
        except Exception as exc:  # pragma: no cover - UI error path
            st.error(f"RTM calculation failed: {exc}")

    st.subheader("Delete RTM row (danger zone)")
    if state.get("mode_effective") != "EDIT":
        st.info("Switch to EDIT mode to delete rows.")
        return
    if rows:
        options = {f"{r['name']} ({r['id']})": r["id"] for r in rows}
        choice = st.selectbox("Row to delete", list(options.keys()))
        confirm = st.checkbox("I understand this will delete the row.")
        text = st.text_input("Type DELETE to confirm", key="rtm_delete_text")
        if st.button("Delete row", disabled=not (confirm and text == "DELETE")):
            try:
                with db.tx(conn):
                    db.delete_rtm_rows(conn, [options[choice]])
                    db.touch_ui_input_meta(
                        conn, panel_id, db.SUBSYSTEM_RTM, note="rtm_row_delete"
                    )
                    db.touch_ui_input_meta(
                        conn, panel_id, db.SUBSYSTEM_PHASE, note="rtm_row_delete"
                    )
                db.update_state_after_write(state, state["db_path"], conn)
                st.success("Row deleted.")
            except Exception as exc:  # pragma: no cover - UI error path
                st.error(f"Failed to delete row: {exc}")
    else:
        st.info("No RTM rows to delete.")
