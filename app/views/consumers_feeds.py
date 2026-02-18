"""Consumers + Feeds page — consumer fields + N feed rows per consumer."""
from __future__ import annotations

import streamlit as st

from app import db
from app.i18n import t


def _role_title(role: dict, lang: str) -> str:
    if lang == "RU":
        return role.get("title_ru") or role.get("code") or role["id"]
    return role.get("title_en") or role.get("title_ru") or role.get("code") or role["id"]


def _section_title(section: dict) -> str:
    no = section.get("section_no")
    base = t("common.section_no", no=int(no) if no is not None else "?")
    label = (section.get("section_label") or section.get("name") or "").strip()
    if label and label.upper() != "DEFAULT":
        return f"{base} ({label})"
    return base


def render(conn, state: dict) -> None:
    st.header(t("consumers.header"))

    panel_id = state.get("selected_panel_id")
    if not panel_id:
        st.info(t("consumers.select_panel"))
        return

    panel = db.get_panel(conn, panel_id)
    if not panel:
        st.warning(t("panels.selected_not_found"))
        return

    is_edit = state.get("mode_effective") == "EDIT"
    lang = state.get("lang", "RU")
    feed_roles = db.list_feed_roles(conn)
    bus_sections = db.list_bus_sections(conn, panel_id)
    consumers = db.list_consumers(conn, panel_id)
    feeds_by_consumer: dict[str, list] = {}
    for f in db.list_consumer_feeds(conn, panel_id):
        cid = f["consumer_id"]
        if cid not in feeds_by_consumer:
            feeds_by_consumer[cid] = []
        feeds_by_consumer[cid].append(f)

    role_options = {r["id"]: _role_title(r, lang) for r in feed_roles}
    bus_options = {bs["id"]: _section_title(bs) for bs in bus_sections}

    if not bus_sections and is_edit:
        st.warning(t("consumers.no_bus_sections"))
    if is_edit and bus_sections:
        with st.expander(t("consumers.sections_editor"), expanded=False):
            with st.form("edit_sections_meta_form"):
                section_updates: list[tuple[str, int, str]] = []
                for idx, bs in enumerate(bus_sections, start=1):
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        section_no = st.number_input(
                            f"{t('consumers.section_no')} ({str(bs['id'])[:8]})",
                            min_value=1,
                            value=int(bs.get("section_no") or idx),
                            step=1,
                            key=f"section_no_{bs['id']}",
                        )
                    with col2:
                        section_label = st.text_input(
                            f"{t('consumers.section_label')} ({str(bs['id'])[:8]})",
                            value=(bs.get("section_label") or bs.get("name") or ""),
                            key=f"section_label_{bs['id']}",
                        )
                    section_updates.append((bs["id"], int(section_no), str(section_label)))
                if st.form_submit_button(t("consumers.save_sections")):
                    try:
                        with db.tx(conn):
                            for section_id, section_no, section_label in section_updates:
                                db.update_bus_section_meta(
                                    conn,
                                    section_id,
                                    section_no=section_no,
                                    section_label=section_label,
                                )
                            db.touch_ui_input_meta(conn, panel_id, db.SUBSYSTEM_SECTIONS, note="edit_sections_meta")
                        db.update_state_after_write(state, state["db_path"], conn)
                        st.success(t("consumers.sections_saved"))
                        st.rerun()
                    except Exception as exc:
                        st.error(t("errors.failed_feed", exc=exc))

    for consumer in consumers:
        cid = consumer["id"]
        feeds = feeds_by_consumer.get(cid, [])

        load_ref_label = (
            t("consumers.load_ref_rtm")
            if consumer.get("load_ref_type") == "RTM_PANEL"
            else t("consumers.load_ref_manual")
        )
        with st.expander(f"{consumer['name']} ({load_ref_label})", expanded=True):
            st.write(t("consumers.name"), consumer["name"])
            st.write(t("consumers.load_ref_type"), consumer["load_ref_type"])
            if consumer["load_ref_type"] == "MANUAL":
                st.write(
                    t(
                        "consumers.power_summary",
                        p=consumer.get("p_kw"),
                        q=consumer.get("q_kvar"),
                        s=consumer.get("s_kva"),
                        i=consumer.get("i_a"),
                    )
                )

            st.subheader(t("consumers.feeds_header"))
            if feeds:
                for idx, feed in enumerate(feeds):
                    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
                    with col1:
                        st.text(bus_options.get(feed["bus_section_id"], feed["bus_section_id"]))
                    with col2:
                        st.text(
                            role_options.get(
                                feed["feed_role_id"],
                                feed["feed_role_id"] or t("common.dash"),
                            )
                        )
                    with col3:
                        st.text(str(feed.get("feed_priority", feed.get("priority", 1))))
                    with col4:
                        if is_edit and st.button(t("consumers.delete_feed"), key=f"del_feed_{feed['id']}"):
                            confirm_key = f"confirm_del_feed_{feed['id']}"
                            if st.session_state.get(confirm_key):
                                try:
                                    with db.tx(conn):
                                        db.delete_consumer_feed(conn, feed["id"])
                                    db.update_state_after_write(state, state["db_path"], conn)
                                    st.success(t("consumers.feed_deleted"))
                                    st.rerun()
                                except Exception as exc:
                                    st.error(t("errors.failed_delete_panel", exc=exc))
                            else:
                                st.session_state[confirm_key] = True
                                st.warning(t("consumers.confirm_delete_feed"))
            else:
                st.caption(t("common.dash"))

            if is_edit and bus_sections and feed_roles:
                with st.form(f"add_feed_{cid}"):
                    bs_id = st.selectbox(
                        t("consumers.bus_section"),
                        options=list(bus_options.keys()),
                        format_func=lambda x: bus_options[x],
                        key=f"feed_bs_{cid}",
                    )
                    fr_id = st.selectbox(
                        t("consumers.feed_role"),
                        options=list(role_options.keys()),
                        format_func=lambda x: role_options[x],
                        key=f"feed_role_{cid}",
                    )
                    priority = st.number_input(
                        t("consumers.feed_priority"),
                        min_value=1,
                        value=len(feeds) + 1,
                        help=t("consumers.tooltip_priority"),
                        key=f"feed_pri_{cid}",
                    )
                    if st.form_submit_button(t("consumers.add_feed")):
                        try:
                            with db.tx(conn):
                                db.upsert_consumer_feed(conn, cid, None, bs_id, fr_id, priority)
                                db.touch_ui_input_meta(conn, panel_id, db.SUBSYSTEM_SECTIONS, note="add_feed")
                            db.update_state_after_write(state, state["db_path"], conn)
                            st.success(t("consumers.saved"))
                            st.rerun()
                        except Exception as exc:
                            st.error(t("errors.failed_feed", exc=exc))

    if is_edit:
        st.subheader(t("consumers.add_consumer"))
        with st.form("add_consumer_form", clear_on_submit=True):
            name = st.text_input(t("consumers.name"))
            load_ref_type = st.radio(
                t("consumers.load_ref_type"),
                ["RTM_PANEL", "MANUAL"],
                format_func=lambda x: t("consumers.load_ref_rtm") if x == "RTM_PANEL" else t("consumers.load_ref_manual"),
            )
            load_ref_id = panel_id if load_ref_type == "RTM_PANEL" else st.text_input(t("consumers.load_ref_id"), value=panel_id)
            p_kw = q_kvar = s_kva = i_a = None
            if load_ref_type == "MANUAL":
                p_kw = st.number_input(t("consumers.p_kw"), min_value=0.0, value=0.0)
                q_kvar = st.number_input(t("consumers.q_kvar"), min_value=0.0, value=0.0)
                s_kva = st.number_input(t("consumers.s_kva"), min_value=0.0, value=0.0)
                i_a = st.number_input(t("consumers.i_a"), min_value=0.0, value=0.0)
            submitted = st.form_submit_button(t("consumers.add_consumer"))

        if submitted and name:
            try:
                with db.tx(conn):
                    db.upsert_consumer(
                        conn,
                        panel_id,
                        {
                            "name": name,
                            "load_ref_type": load_ref_type,
                            "load_ref_id": load_ref_id,
                            "p_kw": p_kw,
                            "q_kvar": q_kvar,
                            "s_kva": s_kva,
                            "i_a": i_a,
                        },
                    )
                    db.touch_ui_input_meta(conn, panel_id, db.SUBSYSTEM_SECTIONS, note="add_consumer")
                db.update_state_after_write(state, state["db_path"], conn)
                st.success(t("consumers.saved"))
                st.rerun()
            except Exception as exc:
                st.error(t("errors.failed_consumer", exc=exc))
        elif submitted and not name:
            st.error(t("validation.name_required"))

    if not consumers:
        st.info(t("consumers.select_panel") if not panel_id else t("consumers.no_consumers"))
