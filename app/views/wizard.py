from __future__ import annotations

import streamlit as st

from app.views import calculate, export, panels, rtm


def render(conn, state: dict) -> None:
    st.header("Wizard (MVP)")
    step = st.radio(
        "Step",
        ["1. Create panel", "2. Add RTM rows", "3. Calculate", "4. Export"],
        horizontal=True,
    )

    if step == "1. Create panel":
        created = panels.render_create_panel(conn, state)
        if created:
            state["selected_panel_id"] = created
            st.success("Panel created. Move to Step 2.")
        return

    if step == "2. Add RTM rows":
        rtm.render(conn, state)
        return

    if step == "3. Calculate":
        calculate.render(conn, state)
        return

    if step == "4. Export":
        export.render(conn, state)
