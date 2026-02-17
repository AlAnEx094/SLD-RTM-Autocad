"""Feed Roles page — view/edit feed role titles."""
from __future__ import annotations

import streamlit as st

from app import db
from app.i18n import t


def _role_title(role: dict, lang: str) -> str:
    if lang == "RU":
        return role.get("title_ru") or role.get("code") or role["id"]
    return role.get("title_en") or role.get("title_ru") or role.get("code") or role["id"]


def render(conn, state: dict) -> None:
    st.header(t("feed_roles.header"))

    roles = db.list_feed_roles(conn)
    if not roles:
        st.info(t("feed_roles.switch_edit") if state.get("mode_effective") != "EDIT" else t("feed_roles.empty"))
        return

    lang = state.get("lang", "RU")
    is_edit = state.get("mode_effective") == "EDIT"

    # Display table (always viewable)
    display_data = [
        {
            t("feed_roles.code"): r["code"],
            t("feed_roles.title_ru"): r.get("title_ru") or "",
            t("feed_roles.title_en"): r.get("title_en") or "",
        }
        for r in roles
    ]
    st.dataframe(display_data, use_container_width=True)

    if not is_edit:
        st.info(t("feed_roles.switch_edit"))
        return

    # Edit form
    st.subheader(t("buttons.edit"))
    role_options = [_role_title(r, lang) for r in roles]
    role_ids = [r["id"] for r in roles]
    selected_idx = st.selectbox(
        t("feed_roles.code"),
        range(len(roles)),
        format_func=lambda i: role_options[i],
    )
    if selected_idx is None:
        return
    role = roles[selected_idx]

    with st.form("edit_feed_role_form"):
        title_ru = st.text_input(
            t("feed_roles.title_ru"),
            value=role.get("title_ru") or "",
        )
        title_en = st.text_input(
            t("feed_roles.title_en"),
            value=role.get("title_en") or "",
        )
        submitted = st.form_submit_button(t("buttons.save"))

    if submitted:
        try:
            with db.tx(conn):
                db.upsert_feed_role_titles(conn, role["id"], title_ru or None, title_en or None)
            db.update_state_after_write(state, state["db_path"], conn)
            st.success(t("feed_roles.saved"))
        except Exception as exc:
            st.error(t("errors.failed_feed_role", exc=exc))
