"""Mode Rules page — per consumer choose active role for NORMAL and EMERGENCY."""
from __future__ import annotations

import streamlit as st

from app import db
from app.i18n import t


def _role_title(role: dict, lang: str) -> str:
    if lang == "RU":
        return role.get("title_ru") or role.get("code") or role["id"]
    return role.get("title_en") or role.get("title_ru") or role.get("code") or role["id"]


def render(conn, state: dict) -> None:
    st.header(t("mode_rules.header"))

    panel_id = state.get("selected_panel_id")
    if not panel_id:
        st.info(t("mode_rules.select_panel"))
        return

    panel = db.get_panel(conn, panel_id)
    if not panel:
        st.warning(t("panels.selected_not_found"))
        return

    is_edit = state.get("mode_effective") == "EDIT"
    lang = state.get("lang", "RU")
    feed_roles = db.list_feed_roles(conn)
    consumers = db.list_consumers(conn, panel_id)
    rules = {((r["consumer_id"], r["mode_id"])): r["active_feed_role_id"] for r in db.list_consumer_mode_rules(conn, panel_id)}

    role_options = {r["id"]: _role_title(r, lang) for r in feed_roles}
    role_ids = list(role_options.keys())

    # Check for consumers without rules
    consumers_without_rules = []
    for c in consumers:
        has_normal = (c["id"], "NORMAL") in rules
        has_emergency = (c["id"], "EMERGENCY") in rules
        if not has_normal or not has_emergency:
            consumers_without_rules.append(c["name"])

    if consumers_without_rules and is_edit:
        st.warning(t("mode_rules.no_rules"))
        if st.button(t("mode_rules.apply_defaults")):
            try:
                with db.tx(conn):
                    n = db.apply_default_mode_rules(conn, panel_id)
                    db.touch_ui_input_meta(conn, panel_id, db.SUBSYSTEM_SECTIONS, note="apply_default_rules")
                db.update_state_after_write(state, state["db_path"], conn)
                st.success(t("mode_rules.defaults_applied", count=n))
                st.rerun()
            except Exception as exc:
                st.error(t("errors.failed_create_panel", exc=exc))

    if not is_edit:
        st.info(t("mode_rules.switch_edit"))

    # Table: consumer | NORMAL role | EMERGENCY role
    rows = []
    for c in consumers:
        cid = c["id"]
        normal_role = rules.get((cid, "NORMAL"), "—")
        emergency_role = rules.get((cid, "EMERGENCY"), "—")
        rows.append({
            t("mode_rules.consumer"): c["name"],
            t("mode_rules.normal_role"): role_options.get(normal_role, normal_role),
            t("mode_rules.emergency_role"): role_options.get(emergency_role, emergency_role),
        })
    if rows:
        st.dataframe(rows, use_container_width=True)

    if is_edit and consumers:
        st.subheader(t("buttons.edit"))
        consumer_options = {c["id"]: c["name"] for c in consumers}
        selected_cid = st.selectbox(
            t("mode_rules.consumer"),
            options=list(consumer_options.keys()),
            format_func=lambda x: consumer_options[x],
        )
        if selected_cid and role_ids:
            normal_role = rules.get((selected_cid, "NORMAL"), "MAIN")
            emergency_role = rules.get((selected_cid, "EMERGENCY"), "RESERVE")
            with st.form("edit_mode_rules_form"):
                norm_idx = role_ids.index(normal_role) if normal_role in role_ids else 0
                emerg_idx = role_ids.index(emergency_role) if emergency_role in role_ids else 0
                new_normal = st.selectbox(
                    t("mode_rules.normal_role"),
                    options=role_ids,
                    index=norm_idx,
                    format_func=lambda x: role_options[x],
                )
                new_emergency = st.selectbox(
                    t("mode_rules.emergency_role"),
                    options=role_ids,
                    index=emerg_idx,
                    format_func=lambda x: role_options[x],
                )
                if st.form_submit_button(t("buttons.save")):
                    try:
                        with db.tx(conn):
                            db.upsert_consumer_mode_rule(conn, selected_cid, "NORMAL", new_normal)
                            db.upsert_consumer_mode_rule(conn, selected_cid, "EMERGENCY", new_emergency)
                            db.touch_ui_input_meta(conn, panel_id, db.SUBSYSTEM_SECTIONS, note="edit_mode_rules")
                        db.update_state_after_write(state, state["db_path"], conn)
                        st.success(t("mode_rules.saved"))
                        st.rerun()
                    except Exception as exc:
                        st.error(t("errors.failed_update_panel", exc=exc))
