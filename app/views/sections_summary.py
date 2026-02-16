"""Sections / Summary page — section_calc separately for NORMAL and EMERGENCY."""
from __future__ import annotations

import streamlit as st

from app import db
from app.i18n import t
from app.ui_components import status_chip


def render(conn, state: dict) -> None:
    st.header(t("sections_summary.header"))

    panel_id = state.get("selected_panel_id")
    if not panel_id:
        st.info(t("sections_summary.select_panel"))
        return

    panel = db.get_panel(conn, panel_id)
    if not panel:
        st.warning(t("panels.selected_not_found"))
        return

    tab_normal, tab_emergency = st.tabs([t("sections_summary.tab_normal"), t("sections_summary.tab_emergency")])

    with tab_normal:
        st.subheader(t("sections_summary.mode_normal"))
        info_normal = db.sections_status(
            conn, panel_id, mode="NORMAL", external_change=state.get("external_change", False)
        )
        status_chip("NORMAL", info_normal, t=t)
        rows_normal = db.list_section_calc(conn, panel_id, "NORMAL")
        if rows_normal:
            st.dataframe(
                [
                    {
                        t("consumers.bus_section"): r.get("bus_section_name") or r["bus_section_id"],
                        "P (kW)": r["p_kw"],
                        "Q (kvar)": r["q_kvar"],
                        "S (kVA)": r["s_kva"],
                        "I (A)": r["i_a"],
                        "updated_at": r.get("updated_at", ""),
                    }
                    for r in rows_normal
                ],
                use_container_width=True,
                disabled=True,
            )
        else:
            st.info(t("sections_summary.no_calc"))
            st.caption(t("sections_summary.run_aggregate"))

    with tab_emergency:
        st.subheader(t("sections_summary.mode_emergency"))
        info_emergency = db.sections_status(
            conn, panel_id, mode="EMERGENCY", external_change=state.get("external_change", False)
        )
        status_chip("EMERGENCY", info_emergency, t=t)
        rows_emergency = db.list_section_calc(conn, panel_id, "EMERGENCY")
        if rows_emergency:
            st.dataframe(
                [
                    {
                        t("consumers.bus_section"): r.get("bus_section_name") or r["bus_section_id"],
                        "P (kW)": r["p_kw"],
                        "Q (kvar)": r["q_kvar"],
                        "S (kVA)": r["s_kva"],
                        "I (A)": r["i_a"],
                        "updated_at": r.get("updated_at", ""),
                    }
                    for r in rows_emergency
                ],
                use_container_width=True,
                disabled=True,
            )
        else:
            st.info(t("sections_summary.no_calc"))
            st.caption(t("sections_summary.run_aggregate"))
