from __future__ import annotations

import streamlit as st

from app import db
from app.views import calculate, export, panels, rtm


def render(conn, state: dict) -> None:
    st.header("Wizard (v0.2)")

    state.setdefault("wizard_step", 0)
    steps = [
        "1) Panel",
        "2) Load Table",
        "3) Calculate",
        "4) Export",
    ]

    cols = st.columns([2, 1, 1])
    with cols[0]:
        st.progress((state["wizard_step"] + 1) / len(steps))
        st.caption(" → ".join([f"[{s}]" if i == state["wizard_step"] else s for i, s in enumerate(steps)]))
    with cols[1]:
        if st.button("Back", disabled=state["wizard_step"] == 0):
            state["wizard_step"] = max(0, state["wizard_step"] - 1)
            st.rerun()
    with cols[2]:
        next_disabled = False
        next_reason = None

        panel_id = state.get("selected_panel_id")
        if state["wizard_step"] == 0:
            if not panel_id or not db.get_panel(conn, panel_id):
                next_disabled = True
                next_reason = "Select or create a panel first."
        elif state["wizard_step"] == 1:
            # Require no validation errors and no unsaved changes.
            if state.get("rtm_dirty", False):
                next_disabled = True
                next_reason = "Save Load Table changes first."
        elif state["wizard_step"] == 2:
            rtm_info = db.rtm_status(conn, panel_id, external_change=state.get("external_change", False)) if panel_id else None
            if not rtm_info or rtm_info.status != "OK":
                next_disabled = True
                next_reason = "Run RTM calculation until status is OK."

        if st.button("Next", disabled=next_disabled):
            state["wizard_step"] = min(len(steps) - 1, state["wizard_step"] + 1)
            st.rerun()
        if next_reason:
            st.caption(next_reason)

    st.divider()

    if state["wizard_step"] == 0:
        st.subheader("Step 1: Select or create a panel")
        panels_list = db.list_panels(conn)
        if panels_list:
            options = [p["id"] for p in panels_list]
            labels = [f"{p['name']} ({p['id'][:8]})" for p in panels_list]
            current = state.get("selected_panel_id")
            idx = options.index(current) if current in options else 0
            choice = st.selectbox("Existing panels", labels, index=idx)
            state["selected_panel_id"] = options[labels.index(choice)]
        created = panels.render_create_panel(conn, state)
        if created:
            state["selected_panel_id"] = created
        return

    if state["wizard_step"] == 1:
        st.subheader("Step 2: Fill Load Table")
        rtm.render(conn, state)
        return

    if state["wizard_step"] == 2:
        st.subheader("Step 3: Calculate")
        calculate.render(conn, state)
        return

    if state["wizard_step"] == 3:
        st.subheader("Step 4: Export")
        export.render(conn, state)
        return
