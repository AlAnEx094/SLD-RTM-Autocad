from __future__ import annotations

from pathlib import Path
import sqlite3

import streamlit as st

from app import db
from app.i18n import t
from app.ui_components import status_chip

ROOT = Path(__file__).resolve().parents[2]


def render(conn, state: dict) -> None:
    st.header(t("calculate.header"))

    panel_id = state.get("selected_panel_id")
    if not panel_id:
        st.info(t("calculate.select_panel"))
        return

    panel = db.get_panel(conn, panel_id)
    if not panel:
        st.warning(t("panels.selected_not_found"))
        return

    if state.get("external_change"):
        st.warning(t("errors.db_modified_outside"))

    rtm_info = db.rtm_status(conn, panel_id, external_change=state.get("external_change", False))
    status_chip("RTM", rtm_info, t=t)

    if panel.get("system_type") == "1PH":
        phase_info = db.phase_status(
            conn,
            panel_id,
            system_type=panel.get("system_type"),
            external_change=state.get("external_change", False),
        )
        status_chip("PHASE", phase_info, t=t)

    du_info = db.du_status(conn, panel_id, external_change=state.get("external_change", False))
    status_chip("DU", du_info, t=t)

    sections_mode = st.radio(t("calculate.sections_mode"), ["NORMAL", "RESERVE"], horizontal=True)
    sections_info = db.sections_status(
        conn,
        panel_id,
        mode=sections_mode,
        external_change=state.get("external_change", False),
    )
    status_chip(f"SECTIONS ({sections_mode})", sections_info, t=t)

    if state.get("mode_effective") != "EDIT":
        st.info(t("calculate.switch_edit"))
        return

    st.subheader(t("calculate.run_rtm"))
    if st.button(t("calculate.recalc_rtm_btn")):
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

    st.subheader(t("calculate.run_du"))
    u_ph_v = panel.get("u_ph_v")
    if u_ph_v is None or float(u_ph_v) <= 0:
        st.error(t("errors.du_blocked"))
    cable_count = db.count_table(conn, "cable_sections")
    if cable_count == 0:
        st.warning(t("calculate.cable_empty"))
        if st.button(t("calculate.seed_cable_btn")):
            try:
                seed_path = ROOT / "db" / "seed_cable_sections.sql"
                with db.tx(conn):
                    db.seed_cable_sections_if_empty(conn, seed_path)
                    db.touch_ui_input_meta(
                        conn, "*", db.SUBSYSTEM_DU, note="seed_cable_sections"
                    )
                db.update_state_after_write(state, state["db_path"], conn)
                st.success(t("calculate.cable_seeded"))
            except Exception as exc:  # pragma: no cover - UI error path
                st.error(t("errors.failed_seed_cable", exc=exc))

    if st.button(t("calculate.recalc_du_btn"), disabled=(u_ph_v is None or float(u_ph_v) <= 0)):
        try:
            from calc_core.voltage_drop import calc_panel_du

            du_conn = sqlite3.connect(state["db_path"])
            try:
                du_conn.row_factory = sqlite3.Row
                du_conn.execute("PRAGMA foreign_keys = ON;")
                count = calc_panel_du(du_conn, panel_id)
            finally:
                du_conn.close()
            db.update_state_after_write(state, state["db_path"])
            st.success(t("calculate.du_recalculated", count=count))
        except Exception as exc:  # pragma: no cover - UI error path
            st.error(t("errors.du_calc_failed", exc=exc))

    st.subheader(t("calculate.run_sections"))
    if st.button(t("calculate.aggregate_btn", mode=sections_mode)):
        try:
            from calc_core.section_aggregation import calc_section_loads

            sec_conn = sqlite3.connect(state["db_path"])
            try:
                sec_conn.row_factory = sqlite3.Row
                sec_conn.execute("PRAGMA foreign_keys = ON;")
                count = calc_section_loads(sec_conn, panel_id, mode=sections_mode)
                sec_conn.commit()
            finally:
                sec_conn.close()
            db.update_state_after_write(state, state["db_path"])
            st.success(t("calculate.sections_aggregated", count=count))
        except Exception as exc:  # pragma: no cover - UI error path
            st.error(t("errors.sections_failed", exc=exc))
