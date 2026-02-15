from __future__ import annotations

import uuid
import streamlit as st

from app import db
from app.validation import validate_panel


def render_create_panel(conn, state: dict) -> str | None:
    st.subheader("Create panel")
    if state.get("mode_effective") != "EDIT":
        st.info("Switch to EDIT mode to create panels.")
        return None

    with st.form("create_panel_form", clear_on_submit=True):
        name = st.text_input("Name")
        system_type = st.selectbox("System type", ("3PH", "1PH"))
        u_ll_v = st.number_input("U LL (V)", min_value=0.0, value=400.0)
        u_ph_v = st.number_input("U PH (V)", min_value=0.0, value=230.0)
        du_limit_lighting_pct = st.number_input(
            "DU limit lighting (%)", min_value=0.0, value=3.0
        )
        du_limit_other_pct = st.number_input(
            "DU limit other (%)", min_value=0.0, value=5.0
        )
        installation_type = st.text_input("Installation type", value="A")
        submitted = st.form_submit_button("Create panel")

    if not submitted:
        return None

    data = {
        "id": str(uuid.uuid4()),
        "name": name,
        "system_type": system_type,
        "u_ll_v": u_ll_v if u_ll_v > 0 else None,
        "u_ph_v": u_ph_v if u_ph_v > 0 else None,
        "du_limit_lighting_pct": du_limit_lighting_pct,
        "du_limit_other_pct": du_limit_other_pct,
        "installation_type": installation_type.strip() or None,
    }
    errors = validate_panel(data)
    if errors:
        st.error("Panel not created: " + "; ".join(errors))
        return None

    try:
        with db.tx(conn):
            panel_id = db.insert_panel(conn, data)
            db.touch_ui_input_meta(conn, panel_id, db.SUBSYSTEM_RTM, note="panel_create")
            db.touch_ui_input_meta(conn, panel_id, db.SUBSYSTEM_PHASE, note="panel_create")
            db.touch_ui_input_meta(conn, panel_id, db.SUBSYSTEM_DU, note="panel_create")
        db.update_state_after_write(state, state["db_path"], conn)
        st.success(f"Panel created: {panel_id}")
        return panel_id
    except Exception as exc:  # pragma: no cover - UI error path
        st.error(f"Failed to create panel: {exc}")
        return None


def render(conn, state: dict) -> None:
    st.header("Panels")

    panels = db.list_panels(conn)
    if panels:
        st.dataframe(panels, use_container_width=True)
    else:
        st.info("No panels found.")

    created = render_create_panel(conn, state)
    if created:
        state["selected_panel_id"] = created

    panel_id = state.get("selected_panel_id")
    if not panel_id:
        st.info("Select a panel to edit.")
        return

    panel = db.get_panel(conn, panel_id)
    if not panel:
        st.warning("Selected panel not found.")
        return

    st.subheader("Panel settings")
    st.text_input("Panel ID", value=panel["id"], disabled=True)

    disabled = state.get("mode_effective") != "EDIT"
    with st.form("edit_panel_form"):
        name = st.text_input("Name", value=panel["name"], disabled=disabled)
        system_type = st.selectbox(
            "System type", ("3PH", "1PH"), index=0 if panel["system_type"] == "3PH" else 1, disabled=disabled
        )
        u_ll_v = st.number_input(
            "U LL (V)",
            min_value=0.0,
            value=float(panel["u_ll_v"]) if panel["u_ll_v"] is not None else 0.0,
            disabled=disabled,
        )
        u_ph_v = st.number_input(
            "U PH (V)",
            min_value=0.0,
            value=float(panel["u_ph_v"]) if panel["u_ph_v"] is not None else 0.0,
            disabled=disabled,
        )
        du_limit_lighting_pct = st.number_input(
            "DU limit lighting (%)",
            min_value=0.0,
            value=float(panel["du_limit_lighting_pct"]),
            disabled=disabled,
        )
        du_limit_other_pct = st.number_input(
            "DU limit other (%)",
            min_value=0.0,
            value=float(panel["du_limit_other_pct"]),
            disabled=disabled,
        )
        installation_type = st.text_input(
            "Installation type",
            value=panel.get("installation_type") or "",
            disabled=disabled,
        )
        submitted = st.form_submit_button("Save panel", disabled=disabled)

    if submitted:
        data = {
            "name": name,
            "system_type": system_type,
            "u_ll_v": u_ll_v if u_ll_v > 0 else None,
            "u_ph_v": u_ph_v if u_ph_v > 0 else None,
            "du_limit_lighting_pct": du_limit_lighting_pct,
            "du_limit_other_pct": du_limit_other_pct,
            "installation_type": installation_type.strip() or None,
        }
        errors = validate_panel(data)
        if errors:
            st.error("Panel not saved: " + "; ".join(errors))
        else:
            try:
                with db.tx(conn):
                    db.update_panel(conn, panel_id, data)
                    db.touch_ui_input_meta(
                        conn, panel_id, db.SUBSYSTEM_RTM, note="panel_edit"
                    )
                    db.touch_ui_input_meta(
                        conn, panel_id, db.SUBSYSTEM_PHASE, note="panel_edit"
                    )
                    db.touch_ui_input_meta(
                        conn, panel_id, db.SUBSYSTEM_DU, note="panel_edit"
                    )
                db.update_state_after_write(state, state["db_path"], conn)
                st.success("Panel updated.")
            except Exception as exc:  # pragma: no cover - UI error path
                st.error(f"Failed to update panel: {exc}")

    st.subheader("Delete panel (danger zone)")
    if state.get("mode_effective") != "EDIT":
        st.info("Switch to EDIT mode to delete panels.")
        return

    deps = db.panel_dependents(conn, panel_id)
    st.write("Dependent rows:")
    st.json(deps)
    confirm = st.checkbox("I understand this will delete the panel and dependents.")
    text = st.text_input("Type DELETE to confirm")
    if st.button("Delete panel", disabled=not (confirm and text == "DELETE")):
        try:
            with db.tx(conn):
                db.delete_panel(conn, panel_id)
            db.update_state_after_write(state, state["db_path"], conn)
            state["selected_panel_id"] = None
            st.success("Panel deleted.")
        except Exception as exc:  # pragma: no cover - UI error path
            st.error(f"Failed to delete panel: {exc}")
