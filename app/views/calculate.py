from __future__ import annotations

import json
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
    pb_mode = st.radio(
        t("phase_balance.pb_mode"),
        ["NORMAL", "EMERGENCY"],
        format_func=lambda x: t("mode.normal") if x == "NORMAL" else t("mode.emergency"),
        horizontal=True,
        key="phase_balance_mode",
    )
    pb_mode_label = t("mode.normal") if pb_mode == "NORMAL" else t("mode.emergency")
    respect_manual = st.checkbox(
        t("phase_balance.respect_manual"),
        value=True,
        key="phase_balance_respect_manual",
    )

    if is_edit and st.button(t("phase_balance.run_btn")):
        try:
            from calc_core.phase_balance import calc_phase_balance

            pb_conn = sqlite3.connect(state["db_path"])
            try:
                pb_conn.row_factory = sqlite3.Row
                pb_conn.execute("PRAGMA foreign_keys = ON;")
                count = calc_phase_balance(
                    pb_conn, panel_id, mode=pb_mode, respect_manual=respect_manual
                )
                pb_conn.commit()
            finally:
                pb_conn.close()
            db.update_state_after_write(state, state["db_path"])
            st.success(t("phase_balance.run_success", count=count))
        except Exception as exc:  # pragma: no cover - UI error path
            st.error(t("phase_balance.run_error", exc=exc))

    balance = db.get_panel_phase_balance(conn, panel_id, mode=pb_mode)
    if balance:
        st.caption(t("phase_balance.totals_caption", mode=pb_mode_label))
        cols = st.columns(4)
        cols[0].metric(t("phase_balance.i_l1"), f"{float(balance['i_l1']):.2f} A")
        cols[1].metric(t("phase_balance.i_l2"), f"{float(balance['i_l2']):.2f} A")
        cols[2].metric(t("phase_balance.i_l3"), f"{float(balance['i_l3']):.2f} A")
        cols[3].metric(t("phase_balance.unbalance_pct"), f"{float(balance['unbalance_pct']):.1f}%")
        st.caption(t("phase_balance.updated_at", at=balance.get("updated_at") or t("common.dash")))
        invalid_count = int(balance.get("invalid_manual_count") or 0) if isinstance(balance, dict) else 0
        raw = balance.get("warnings_json")
        items: list[dict] = []
        if raw:
            try:
                parsed = json.loads(str(raw))
                if isinstance(parsed, list):
                    items = [x for x in parsed if isinstance(x, dict)]
            except Exception:
                items = []

        # v0.3a panel-level warning: EMERGENCY sections not computed -> fallback used.
        if any(str(it.get("reason") or "").strip().upper() == "EMERGENCY_SECTIONS_NOT_COMPUTED" for it in items):
            st.warning(t("phase_balance.emergency_sections_not_computed"))

        if invalid_count > 0:
            st.warning(t("phase_balance.invalid_manual_banner", count=invalid_count))

        # Details expander only when we have circuit-level items.
        circuit_items = [
            it
            for it in items
            if str(it.get("reason") or "").strip().upper() != "EMERGENCY_SECTIONS_NOT_COMPUTED"
        ]
        if invalid_count > 0:
            if not circuit_items:
                st.caption(t("phase_balance.invalid_manual_no_details"))
            else:
                with st.expander(
                    t("phase_balance.invalid_manual_expander", count=invalid_count),
                    expanded=False,
                ):
                    def _reason_label(code: object) -> str:
                        c = str(code or "").strip().upper()
                        if c == "MANUAL_INVALID_PHASE":
                            return t("phase_balance.reason_manual_invalid_phase")
                        if c == "EMERGENCY_SECTIONS_NOT_COMPUTED":
                            return t("phase_balance.reason_emergency_sections_not_computed")
                        return c or t("common.dash")

                    st.dataframe(
                        [
                            {
                                t("phase_balance.col_id"): it.get("circuit_id") or "",
                                t("phase_balance.col_name"): it.get("name") or "",
                                t("phase_balance.col_i_calc_a"): it.get("i_a"),
                                t("phase_balance.col_phase"): it.get("phase") or "",
                                t("phase_balance.col_reason"): _reason_label(it.get("reason")),
                            }
                            for it in circuit_items
                        ],
                        use_container_width=True,
                    )

    circuits = db.list_circuits(conn, panel_id)
    circuits_1ph = [c for c in circuits if c.get("phases") == 1]
    if not circuits_1ph:
        st.info(t("phase_balance.no_1ph_circuits"))
        return

    if pb_mode == "EMERGENCY":
        unset_count = sum(1 for c in circuits_1ph if not c.get("bus_section_id"))
        if unset_count > 0:
            st.warning(t("phase_balance.emergency_bus_section_unset", count=unset_count))

    def _phase_source_label(src: str) -> str:
        if src == "MANUAL":
            return t("phase_balance.phase_source_manual")
        return t("phase_balance.phase_source_auto")

    bus_sections = db.list_bus_sections(conn, panel_id)
    # Use stable labels to avoid ambiguity in dropdown.
    section_label_by_id = {s["id"]: f"{s['name']} ({str(s['id'])[:8]})" for s in bus_sections}
    section_id_by_label = {v: k for k, v in section_label_by_id.items()}
    section_labels = sorted(section_label_by_id.values())

    df = pd.DataFrame(
        [
            {
                "id": c["id"],
                "name": c.get("name") or "",
                "phases": int(c["phases"]),
                "i_calc_a": float(c["i_calc_a"]),
                "bus_section": (
                    section_label_by_id.get(c.get("bus_section_id"))
                    if c.get("bus_section_id")
                    else ""
                ),
                "phase": c.get("phase") or "",
                "status": (
                    t("phase_balance.status_invalid_manual")
                    if (str(c.get("phase_source") or "AUTO").strip().upper() == "MANUAL")
                    and (str(c.get("phase") or "").strip().upper() not in ("L1", "L2", "L3"))
                    else ""
                ),
                "phase_source": _phase_source_label(
                    (c.get("phase_source") or "AUTO").strip().upper()
                ),
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
        "bus_section": st.column_config.SelectboxColumn(
            t("phase_balance.col_bus_section"),
            options=["", *section_labels],
            required=False,
            default="",
            disabled=not is_edit,
        ),
        "phase": st.column_config.SelectboxColumn(
            t("phase_balance.col_phase"),
            options=phase_options,
            required=False,
            default="",
            disabled=not is_edit,
        ),
        "status": st.column_config.TextColumn(
            t("phase_balance.col_status"),
            disabled=True,
        ),
        "phase_source": st.column_config.TextColumn(
            t("phase_balance.col_phase_source"), disabled=True
        ),
    }

    edited = st.data_editor(
        df,
        column_config=col_config,
        use_container_width=True,
        key="phase_balance_circuits",
        disabled=["id", "name", "phases", "i_calc_a", "status", "phase_source"],
    )

    if is_edit and st.button(t("phase_balance.save_phases_btn")):
        try:
            orig_by_id = {
                c["id"]: (
                    ((c.get("phase") or "").strip() or None),
                    (c.get("bus_section_id") or None),
                )
                for c in circuits_1ph
            }
            with db.tx(conn):
                for _, row in edited.iterrows():
                    circ_id = row["id"]
                    new_phase = row.get("phase") or ""
                    new_phase = str(new_phase).strip() if new_phase else None
                    if new_phase == "":
                        new_phase = None
                    new_bus_label = row.get("bus_section") or ""
                    new_bus_label = str(new_bus_label).strip() if new_bus_label else ""
                    new_bus_id = section_id_by_label.get(new_bus_label) if new_bus_label else None

                    orig_phase, orig_bus = orig_by_id.get(circ_id, (None, None))
                    phase_changed = orig_phase != new_phase
                    bus_changed = orig_bus != new_bus_id
                    if phase_changed:
                        db.update_circuit_phase(
                            conn, circ_id, new_phase, phase_source="MANUAL"
                        )
                    if bus_changed:
                        db.update_circuit_bus_section(conn, circ_id, new_bus_id)
                db.touch_ui_input_meta(conn, panel_id, db.SUBSYSTEM_PHASE, note="phase_balance_edit")
            db.update_state_after_write(state, state["db_path"], conn)
            st.success(t("phase_balance.save_success"))
        except Exception as exc:  # pragma: no cover - UI error path
            st.error(t("phase_balance.save_error", exc=exc))
