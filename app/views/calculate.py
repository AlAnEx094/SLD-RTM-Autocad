from __future__ import annotations

from pathlib import Path
import sqlite3

import streamlit as st

from app import db

ROOT = Path(__file__).resolve().parents[2]


def _render_status(label: str, info: db.StatusInfo) -> None:
    if info.status == "OK":
        st.success(f"{label}: OK")
    elif info.status == "STALE":
        st.warning(f"{label}: STALE")
    elif info.status == "NO_CALC":
        st.error(f"{label}: NO_CALC")
    elif info.status == "UNKNOWN":
        st.warning(f"{label}: UNKNOWN")
    else:
        st.info(f"{label}: {info.status}")
    if info.calc_updated_at:
        st.caption(f"{label} updated_at: {info.calc_updated_at}")


def render(conn, state: dict) -> None:
    st.header("Calculate")

    panel_id = state.get("selected_panel_id")
    if not panel_id:
        st.info("Select a panel to run calculations.")
        return

    panel = db.get_panel(conn, panel_id)
    if not panel:
        st.warning("Selected panel not found.")
        return

    if state.get("external_change"):
        st.warning(
            "DB was modified outside UI. Status is UNKNOWN; recalculation recommended."
        )

    rtm_info = db.rtm_status(conn, panel_id, external_change=state.get("external_change", False))
    _render_status("RTM", rtm_info)

    if panel.get("system_type") == "1PH":
        phase_info = db.phase_status(
            conn,
            panel_id,
            system_type=panel.get("system_type"),
            external_change=state.get("external_change", False),
        )
        _render_status("PHASE", phase_info)

    du_info = db.du_status(conn, panel_id, external_change=state.get("external_change", False))
    _render_status("DU", du_info)

    sections_mode = st.radio("Sections mode", ["NORMAL", "RESERVE"], horizontal=True)
    sections_info = db.sections_status(
        conn,
        panel_id,
        mode=sections_mode,
        external_change=state.get("external_change", False),
    )
    _render_status(f"SECTIONS ({sections_mode})", sections_info)

    if state.get("mode_effective") != "EDIT":
        st.info("Switch to EDIT mode to run calculations.")
        return

    st.subheader("Run RTM")
    if st.button("Recalculate RTM"):
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

    st.subheader("Run DU (voltage drop)")
    u_ph_v = panel.get("u_ph_v")
    if u_ph_v is None or float(u_ph_v) <= 0:
        st.error("Panel u_ph_v is missing or invalid. DU calculation is blocked.")
    cable_count = db.count_table(conn, "cable_sections")
    if cable_count == 0:
        st.warning("cable_sections is empty. Seed required for DU.")
        if st.button("Seed cable sections"):
            try:
                seed_path = ROOT / "db" / "seed_cable_sections.sql"
                with db.tx(conn):
                    db.seed_cable_sections_if_empty(conn, seed_path)
                    db.touch_ui_input_meta(
                        conn, "*", db.SUBSYSTEM_DU, note="seed_cable_sections"
                    )
                db.update_state_after_write(state, state["db_path"], conn)
                st.success("Cable sections seeded.")
            except Exception as exc:  # pragma: no cover - UI error path
                st.error(f"Failed to seed cable sections: {exc}")

    if st.button("Recalculate DU", disabled=(u_ph_v is None or float(u_ph_v) <= 0)):
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
            st.success(f"DU recalculated for {count} circuits.")
        except Exception as exc:  # pragma: no cover - UI error path
            st.error(f"DU calculation failed: {exc}")

    st.subheader("Run Sections")
    if st.button(f"Aggregate sections ({sections_mode})"):
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
            st.success(f"Sections aggregated: {count}")
        except Exception as exc:  # pragma: no cover - UI error path
            st.error(f"Sections aggregation failed: {exc}")
