from __future__ import annotations

import sys
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db  # noqa: E402
from app.i18n import t  # noqa: E402
from app.views import (  # noqa: E402
    calculate,
    consumers_feeds,
    db_connect,
    export,
    feed_roles,
    mode_rules,
    overview,
    panels,
    rtm,
    sections_summary,
    wizard,
)


DEFAULT_DB_PATH = str(ROOT / "db" / "project.sqlite")


def _init_state() -> None:
    state = st.session_state
    state.setdefault("db_path", DEFAULT_DB_PATH)
    state.setdefault("lang", "RU")
    state.setdefault("mode", "READ_ONLY")
    state.setdefault("edit_confirm", False)
    state.setdefault("selected_panel_id", None)
    state.setdefault("data_version", None)
    state.setdefault("db_mtime", None)
    state.setdefault("external_change", False)
    state.setdefault("pending_write_refresh", False)


def _detect_external_change(state: dict, db_path: str, conn) -> None:
    current_version = db.get_data_version(conn)
    current_mtime = db.get_db_mtime(db_path)
    external = False
    if state.get("data_version") is not None:
        if current_version != state["data_version"] or (
            state.get("db_mtime") is not None
            and current_mtime is not None
            and current_mtime != state["db_mtime"]
        ):
            if not state.get("pending_write_refresh", False):
                external = True
    state["data_version"] = current_version
    state["db_mtime"] = current_mtime
    state["external_change"] = external
    state["pending_write_refresh"] = False


def main() -> None:
    st.set_page_config(page_title="SLD-RTM UI", layout="wide")
    _init_state()
    state = st.session_state

    with st.sidebar:
        st.title(t("app.title"))
        st.text_input(t("sidebar.db_path"), key="db_path")
        mode_labels = [t("access_mode.read_only"), t("access_mode.edit")]
        mode_idx = 0 if state["mode"] == "READ_ONLY" else 1
        mode_choice = st.radio(t("sidebar.access_mode"), mode_labels, index=mode_idx)
        state["mode"] = "READ_ONLY" if mode_choice == mode_labels[0] else "EDIT"
        if state["mode"] == "EDIT":
            st.checkbox(t("access_mode.confirm_edit"), key="edit_confirm")
        mode_effective = "EDIT" if state["mode"] == "EDIT" and state["edit_confirm"] else "READ_ONLY"
        state["mode_effective"] = mode_effective

        lang_choice = st.radio(
            t("sidebar.language"),
            [t("sidebar.lang_ru"), t("sidebar.lang_en")],
            index=0 if state.get("lang", "RU") == "RU" else 1,
        )
        state["lang"] = "RU" if lang_choice == t("sidebar.lang_ru") else "EN"

    db_path = state["db_path"]
    if not Path(db_path).exists():
        st.error(t("errors.db_not_found", path=db_path))
        st.info(t("errors.go_db_connect"))
        db_connect.render(None, state)
        return

    conn = None
    try:
        conn = db.connect(db_path, read_only=mode_effective != "EDIT")
    except Exception as exc:  # pragma: no cover - UI error path
        st.error(t("errors.failed_connect", exc=exc))
        return

    try:
        if mode_effective == "EDIT":
            db.ensure_ui_input_meta(conn)

        _detect_external_change(state, db_path, conn)

        schema = db.schema_status(conn)
        if schema["missing_tables"] or schema.get("missing_columns"):
            st.error(t("errors.schema_incompatible"))
            db_connect.render(conn, state)
            return

        if state.get("external_change"):
            st.warning(t("errors.db_changed_outside"))

        panels_list = db.list_panels(conn)
        panel_options = [t("sidebar.none")] + [
            f"{p['name']} ({p['id'][:8]})" for p in panels_list
        ]
        panel_ids = [None] + [p["id"] for p in panels_list]
        with st.sidebar:
            selected = st.selectbox(
                t("sidebar.active_panel"),
                options=panel_options,
                index=panel_ids.index(state.get("selected_panel_id"))
                if state.get("selected_panel_id") in panel_ids
                else 0,
            )
            state["selected_panel_id"] = panel_ids[panel_options.index(selected)]

            nav_options = [
                t("nav.db_connect"),
                t("nav.overview"),
                t("nav.wizard"),
                t("nav.panels"),
                t("nav.rtm"),
                t("nav.calculate"),
                t("nav.feed_roles"),
                t("nav.consumers_feeds"),
                t("nav.mode_rules"),
                t("nav.sections_summary"),
                t("nav.export"),
            ]
            page = st.radio(t("sidebar.navigation"), nav_options)

        pages = {
            t("nav.db_connect"): db_connect,
            t("nav.overview"): overview,
            t("nav.wizard"): wizard,
            t("nav.panels"): panels,
            t("nav.rtm"): rtm,
            t("nav.calculate"): calculate,
            t("nav.feed_roles"): feed_roles,
            t("nav.consumers_feeds"): consumers_feeds,
            t("nav.mode_rules"): mode_rules,
            t("nav.sections_summary"): sections_summary,
            t("nav.export"): export,
        }

        pages[page].render(conn, state)
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    main()
