from __future__ import annotations

import sys
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db  # noqa: E402
from app.views import (  # noqa: E402
    calculate,
    db_connect,
    export,
    overview,
    panels,
    rtm,
    wizard,
)


DEFAULT_DB_PATH = str(ROOT / "db" / "project.sqlite")


def _init_state() -> None:
    state = st.session_state
    state.setdefault("db_path", DEFAULT_DB_PATH)
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
        st.title("SLD-RTM UI")
        st.text_input("DB path", key="db_path")
        st.radio("Mode", ["READ_ONLY", "EDIT"], key="mode")
        if state["mode"] == "EDIT":
            st.checkbox("I understand this will modify DB", key="edit_confirm")
        mode_effective = "EDIT" if state["mode"] == "EDIT" and state["edit_confirm"] else "READ_ONLY"
        state["mode_effective"] = mode_effective

    db_path = state["db_path"]
    if not Path(db_path).exists():
        st.error(f"DB not found: {db_path}")
        st.info("Go to DB Connect to create/apply migrations.")
        db_connect.render(None, state)
        return

    conn = None
    try:
        conn = db.connect(db_path, read_only=mode_effective != "EDIT")
    except Exception as exc:  # pragma: no cover - UI error path
        st.error(f"Failed to connect: {exc}")
        return

    try:
        if mode_effective == "EDIT":
            db.ensure_ui_input_meta(conn)

        _detect_external_change(state, db_path, conn)

        if state.get("external_change"):
            st.warning(
                "DB changed outside UI. Status is UNKNOWN until recalculation."
            )

        panels_list = db.list_panels(conn)
        panel_options = ["(none)"] + [
            f"{p['name']} ({p['id'][:8]})" for p in panels_list
        ]
        panel_ids = [None] + [p["id"] for p in panels_list]
        with st.sidebar:
            selected = st.selectbox(
                "Active panel",
                options=panel_options,
                index=panel_ids.index(state.get("selected_panel_id"))
                if state.get("selected_panel_id") in panel_ids
                else 0,
            )
            state["selected_panel_id"] = panel_ids[panel_options.index(selected)]

            page = st.radio(
                "Navigation",
                [
                    "DB Connect",
                    "Overview",
                    "Wizard",
                    "Panels",
                    "RTM",
                    "Calculate",
                    "Export",
                ],
            )

        pages = {
            "DB Connect": db_connect,
            "Overview": overview,
            "Wizard": wizard,
            "Panels": panels,
            "RTM": rtm,
            "Calculate": calculate,
            "Export": export,
        }

        pages[page].render(conn, state)
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    main()
