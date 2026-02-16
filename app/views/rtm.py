from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd
import streamlit as st

from app import db
from app.i18n import t
from app.ui_components import status_chip
from app.validation import validate_panel_for_rtm, validate_rtm_rows


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


def _normalize_input_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "id" in out.columns:
        out["id"] = out["id"].where(out["id"].notna(), None)
        out["id"] = out["id"].astype(str).replace({"None": ""})
    for col in ("name", "phase_mode", "phase_fixed"):
        if col in out.columns:
            out[col] = out[col].where(out[col].notna(), "")
            out[col] = out[col].astype(str).str.strip()
    for col in ("n", "phases"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in ("pn_kw", "ki", "cos_phi", "tg_phi"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    cols = [c for c in INPUT_COLUMNS if c in out.columns]
    out = out[cols]
    if "id" in out.columns:
        out = out.sort_values(by=["id", "name"], kind="stable").reset_index(drop=True)
    else:
        out = out.sort_values(by=["name"], kind="stable").reset_index(drop=True)
    return out


def render(conn, state: dict) -> None:
    st.header(t("rtm.header"))

    panel_id = state.get("selected_panel_id")
    if not panel_id:
        st.info(t("rtm.select_panel"))
        return

    panel = db.get_panel(conn, panel_id)
    if not panel:
        st.warning(t("panels.selected_not_found"))
        return

    # Panel header / quick settings
    with st.expander(t("rtm.panel_header"), expanded=True):
        st.write(t("rtm.panel_info", name=panel.get("name") or "", id=panel_id))
        if state.get("mode_effective") == "EDIT":
            with st.form("load_table_panel_form"):
                name = st.text_input(t("panels.name"), value=str(panel.get("name") or ""))
                system_type = st.selectbox(
                    t("panels.system_type"), ("3PH", "1PH"),
                    index=0 if panel.get("system_type") == "3PH" else 1,
                )
                u_ll_v = st.number_input(
                    t("panels.u_ll"), min_value=0.0,
                    value=float(panel["u_ll_v"]) if panel.get("u_ll_v") is not None else 0.0,
                )
                u_ph_v = st.number_input(
                    t("panels.u_ph"), min_value=0.0,
                    value=float(panel["u_ph_v"]) if panel.get("u_ph_v") is not None else 0.0,
                )
                submitted = st.form_submit_button(t("rtm.save_header_btn"))
            if submitted:
                data = {
                    "name": name.strip(),
                    "system_type": system_type,
                    "u_ll_v": u_ll_v if u_ll_v > 0 else None,
                    "u_ph_v": u_ph_v if u_ph_v > 0 else None,
                    "du_limit_lighting_pct": panel.get("du_limit_lighting_pct"),
                    "du_limit_other_pct": panel.get("du_limit_other_pct"),
                    "installation_type": panel.get("installation_type"),
                }
                # Keep panel validation consistent with Panels page rules.
                # (RTM-specific voltage gating is handled separately.)
                from app.validation import validate_panel

                panel_errors = validate_panel(data, translator=t)
                if panel_errors:
                    st.error(t("rtm.header_not_saved", errors="; ".join(panel_errors)))
                else:
                    try:
                        with db.tx(conn):
                            db.update_panel(conn, panel_id, data)
                            db.touch_ui_input_meta(conn, panel_id, db.SUBSYSTEM_RTM, note="panel_edit_load_table")
                            db.touch_ui_input_meta(conn, panel_id, db.SUBSYSTEM_PHASE, note="panel_edit_load_table")
                            db.touch_ui_input_meta(conn, panel_id, db.SUBSYSTEM_DU, note="panel_edit_load_table")
                        db.update_state_after_write(state, state["db_path"], conn)
                        st.success(t("rtm.header_updated"))
                        panel = db.get_panel(conn, panel_id) or panel
                    except Exception as exc:  # pragma: no cover
                        st.error(t("errors.failed_update_panel", exc=exc))
        else:
            st.caption(t("rtm.switch_edit_header"))

    rtm_info = db.rtm_status(conn, panel_id, external_change=state.get("external_change", False))
    phase_info = db.phase_status(
        conn,
        panel_id,
        system_type=panel.get("system_type"),
        external_change=state.get("external_change", False),
    )
    status_chip(t("chips.rtm"), rtm_info, t=t)
    if panel.get("system_type") == "1PH":
        status_chip(t("chips.phase"), phase_info, t=t)

    rows = db.list_rtm_rows_with_calc(conn, panel_id)
    df_full = pd.DataFrame(rows)
    if df_full.empty:
        df_full = pd.DataFrame(columns=INPUT_COLUMNS + CALC_COLUMNS)

    # Normalize enums for editing UX
    for col in ("phase_mode", "phase_fixed"):
        if col in df_full.columns:
            df_full[col] = df_full[col].where(df_full[col].notna(), "")
            df_full[col] = df_full[col].astype(str).str.upper().replace({"NAN": ""})
            if col == "phase_fixed":
                df_full[col] = df_full[col].replace({"NONE": ""})

    with st.container():
        tabs = st.tabs([t("rtm.tab_edit"), t("rtm.tab_filtered")])
        with tabs[0]:
            input_validation = validate_rtm_rows(df_full[INPUT_COLUMNS].copy(), translator=t)
            df_full["row_status"] = df_full.index.map(
                lambda i: input_validation.row_status.get(i, "OK")
            )

            st.caption(t("rtm.edit_caption"))
            edited_df = st.data_editor(
                df_full[INPUT_COLUMNS + CALC_COLUMNS + ["row_status"]],
                num_rows="dynamic",
                disabled=CALC_COLUMNS + ["row_status", "id"],
                use_container_width=True,
                key="rtm_editor",
            )

            input_df = edited_df[INPUT_COLUMNS].copy()
            validation = validate_rtm_rows(input_df, translator=t)
            if validation.warnings:
                st.warning(t("rtm.warnings", text="\n".join(validation.warnings)))
            if validation.errors:
                st.error(t("rtm.validation_errors", text="\n".join(validation.errors)))

            # Dirty detection vs DB snapshot (strict gating for calc/export).
            original_norm = _normalize_input_df(df_full[INPUT_COLUMNS].copy())
            edited_norm = _normalize_input_df(input_df.copy())
            dirty = not original_norm.equals(edited_norm)
            state["rtm_dirty"] = dirty
            if dirty:
                st.warning(t("rtm.unsaved_changes"))

            can_save = (not validation.has_errors) and state.get("mode_effective") == "EDIT"
            if st.button(t("rtm.save_changes_btn"), disabled=not can_save):
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
                                "cos_phi": None
                                if cos_phi in (None, "") or pd.isna(cos_phi)
                                else float(cos_phi),
                                "tg_phi": None
                                if tg_phi in (None, "") or pd.isna(tg_phi)
                                else float(tg_phi),
                                "phases": int(float(row.get("phases"))),
                                "phase_mode": str(row.get("phase_mode") or "")
                                .strip()
                                .upper(),
                                "phase_fixed": str(row.get("phase_fixed") or "")
                                .strip()
                                .upper()
                                or None,
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
                    state["rtm_dirty"] = False
                    st.success(t("rtm.rows_saved"))
                except Exception as exc:  # pragma: no cover - UI error path
                    st.error(t("errors.failed_save_rtm", exc=exc))

        with tabs[1]:
            search = st.text_input(t("rtm.search"))
            phase_filter = st.multiselect(t("rtm.phases"), [1, 3], default=[1, 3])
            mode_filter = st.multiselect(
                t("rtm.phase_mode"), ["AUTO", "FIXED", "NONE"], default=["AUTO", "FIXED", "NONE"]
            )
            view_df = df_full.copy()
            if search:
                view_df = view_df[
                    view_df["name"].astype(str).str.contains(search, case=False, na=False)
                ]
            if phase_filter:
                view_df = view_df[view_df["phases"].isin(phase_filter)]
            if mode_filter:
                view_df = view_df[view_df["phase_mode"].isin(mode_filter)]
            st.dataframe(view_df, use_container_width=True)

    st.subheader(t("rtm.input_totals"))
    if df_full.empty:
        st.info(t("rtm.no_input_rows"))
    else:
        pn_total = (df_full["n"].astype(float) * df_full["pn_kw"].astype(float)).sum()
        ki_pn = (
            df_full["ki"].astype(float)
            * df_full["n"].astype(float)
            * df_full["pn_kw"].astype(float)
        ).sum()
        cols = st.columns(2)
        cols[0].metric(t("rtm.sum_pn_total"), f"{pn_total:.3f}")
        cols[1].metric(t("rtm.sum_ki_pn"), f"{ki_pn:.3f}")

    st.subheader(t("rtm.panel_calc_header"))
    panel_calc = db.get_rtm_panel_calc(conn, panel_id)
    if panel_calc:
        st.dataframe(panel_calc, use_container_width=True)
    else:
        st.info(t("rtm.panel_calc_empty"))

    if panel.get("system_type") == "1PH":
        st.subheader(t("rtm.phase_balance_header"))
        phase_calc = db.get_panel_phase_calc(conn, panel_id)
        if phase_calc:
            st.dataframe(phase_calc, use_container_width=True)
        else:
            st.info(t("rtm.phase_calc_empty"))

    st.subheader(t("rtm.recalc_header"))
    panel_rtm_errors = validate_panel_for_rtm(panel, translator=t)
    if panel_rtm_errors:
        st.error(t("rtm.panel_validation", errors="; ".join(panel_rtm_errors)))

    can_recalc = (
        state.get("mode_effective") == "EDIT"
        and not state.get("rtm_dirty", False)
        and (not validate_rtm_rows(df_full[INPUT_COLUMNS].copy()).has_errors)
        and len(df_full) > 0
        and not panel_rtm_errors
    )

    if st.button(t("rtm.recalc_btn"), disabled=not can_recalc):
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
                    st.warning(t("errors.phase_balance_skipped", exc=exc))

            db.update_state_after_write(state, state["db_path"])
            st.success(t("rtm.recalculated"))
        except Exception as exc:  # pragma: no cover - UI error path
            st.error(t("errors.rtm_calc_failed", exc=exc))

    st.subheader(t("rtm.delete_header"))
    if state.get("mode_effective") != "EDIT":
        st.info(t("rtm.switch_edit_delete"))
        return
    if rows:
        options = {f"{r['name']} ({r['id']})": r["id"] for r in rows}
        choice = st.selectbox(t("rtm.row_to_delete"), list(options.keys()))
        confirm = st.checkbox(t("rtm.delete_row_confirm"))
        text = st.text_input(t("panels.type_delete"), key="rtm_delete_text")
        if st.button(t("rtm.delete_row_btn"), disabled=not (confirm and text == "DELETE")):
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
                st.success(t("rtm.row_deleted"))
            except Exception as exc:  # pragma: no cover - UI error path
                st.error(t("errors.failed_delete_row", exc=exc))
    else:
        st.info(t("rtm.no_rows_to_delete"))
