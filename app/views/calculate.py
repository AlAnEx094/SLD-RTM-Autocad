from __future__ import annotations

from pathlib import Path
import sqlite3

import pandas as pd
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
    status_chip(t("chips.rtm"), rtm_info, t=t)

    if panel.get("system_type") == "1PH":
        phase_info = db.phase_status(
            conn,
            panel_id,
            system_type=panel.get("system_type"),
            external_change=state.get("external_change", False),
        )
        status_chip(t("chips.phase"), phase_info, t=t)

    du_info = db.du_status(conn, panel_id, external_change=state.get("external_change", False))
    status_chip(t("chips.du"), du_info, t=t)

    sections_mode = st.radio(
        t("calculate.sections_mode"),
        ["NORMAL", "EMERGENCY"],
        format_func=lambda x: t("mode.normal") if x == "NORMAL" else t("mode.emergency"),
        horizontal=True,
    )
    sections_info = db.sections_status(
        conn,
        panel_id,
        mode=sections_mode,
        external_change=state.get("external_change", False),
    )
    sections_mode_label = t("mode.normal") if sections_mode == "NORMAL" else t("mode.emergency")
    status_chip(t("chips.sections_with_mode", mode=sections_mode_label), sections_info, t=t)

    if panel.get("system_type") == "1PH":
        _render_phase_balance_section(conn, state, panel_id, panel)

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
    if st.button(t("calculate.aggregate_btn", mode=sections_mode_label)):
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


def _render_phase_balance_section(conn, state: dict, panel_id: str, panel: dict) -> None:
    """Phase balance section: Run button, totals, circuits table (1PH only)."""
    st.subheader(t("phase_balance.section"))

    is_edit = state.get("mode_effective") == "EDIT"

    if is_edit and st.button(t("phase_balance.run_btn")):
        try:
            from calc_core.phase_balance import calc_phase_balance

            pb_conn = sqlite3.connect(state["db_path"])
            try:
                pb_conn.row_factory = sqlite3.Row
                pb_conn.execute("PRAGMA foreign_keys = ON;")
                count = calc_phase_balance(pb_conn, panel_id, mode="NORMAL")
                pb_conn.commit()
            finally:
                pb_conn.close()
            db.update_state_after_write(state, state["db_path"])
            st.success(t("phase_balance.run_success", count=count))
        except Exception as exc:  # pragma: no cover - UI error path
            st.error(t("phase_balance.run_error", exc=exc))

    balance = db.get_panel_phase_balance(conn, panel_id, mode="NORMAL")
    if balance:
        st.caption(t("phase_balance.totals_caption"))
        cols = st.columns(4)
        cols[0].metric(t("phase_balance.i_l1"), f"{float(balance['i_l1']):.2f} A")
        cols[1].metric(t("phase_balance.i_l2"), f"{float(balance['i_l2']):.2f} A")
        cols[2].metric(t("phase_balance.i_l3"), f"{float(balance['i_l3']):.2f} A")
        cols[3].metric(t("phase_balance.unbalance_pct"), f"{float(balance['unbalance_pct']):.1f}%")
        st.caption(t("phase_balance.updated_at", at=balance.get("updated_at") or t("common.dash")))

    circuits = db.list_circuits(conn, panel_id)
    circuits_1ph = [c for c in circuits if c.get("phases") == 1]
    if not circuits_1ph:
        st.info(t("phase_balance.no_1ph_circuits"))
        return

    df = pd.DataFrame(
        [
            {
                "id": c["id"],
                "name": c.get("name") or "",
                "phases": int(c["phases"]),
                "i_calc_a": float(c["i_calc_a"]),
                "phase": c.get("phase") or "",
            }
            for c in circuits_1ph
        ]
    )

    phase_options = ["", "L1", "L2", "L3"]
    col_config = {
        "id": st.column_config.TextColumn(t("phase_balance.col_id"), disabled=True),
        "name": st.column_config.TextColumn(t("phase_balance.col_name"), disabled=True),
        "phases": st.column_config.NumberColumn(t("phase_balance.col_phases"), disabled=True),
        "i_calc_a": st.column_config.NumberColumn(
            t("phase_balance.col_i_calc_a"), format="%.2f", disabled=True
        ),
        "phase": st.column_config.SelectboxColumn(
            t("phase_balance.col_phase"),
            options=phase_options,
            required=False,
            default="",
            disabled=not is_edit,
        ),
    }

    edited = st.data_editor(
        df,
        column_config=col_config,
        use_container_width=True,
        key="phase_balance_circuits",
        disabled=["id", "name", "phases", "i_calc_a"],
    )

    if is_edit and st.button(t("phase_balance.save_phases_btn")):
        try:
            with db.tx(conn):
                for _, row in edited.iterrows():
                    circ_id = row["id"]
                    new_phase = row.get("phase") or ""
                    new_phase = str(new_phase).strip() if new_phase else None
                    if new_phase == "":
                        new_phase = None
                    db.update_circuit_phase(conn, circ_id, new_phase)
                db.touch_ui_input_meta(conn, panel_id, db.SUBSYSTEM_PHASE, note="phase_balance_edit")
            db.update_state_after_write(state, state["db_path"], conn)
            st.success(t("phase_balance.save_success"))
        except Exception as exc:  # pragma: no cover - UI error path
            st.error(t("phase_balance.save_error", exc=exc))
