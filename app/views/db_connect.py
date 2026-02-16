from __future__ import annotations

from pathlib import Path
import shutil
from datetime import datetime
import streamlit as st

from app import db
from app.i18n import t


def render(conn, state: dict) -> None:
    st.header(t("db_connect.header"))

    db_path = state.get("db_path")
    st.write(t("db_connect.current_path", path=db_path))

    if not db_path:
        st.error(t("errors.db_path_empty"))
        return

    if not Path(db_path).exists():
        st.warning(t("db_connect.file_not_exists"))
        st.info(t("db_connect.use_edit_mode"))
        if state.get("mode_effective") != "EDIT":
            return

        st.subheader(t("db_connect.create_header"))
        confirm = st.checkbox(t("db_connect.create_confirm"))
        if st.button(t("db_connect.create_btn"), disabled=not confirm):
            try:
                from tools.run_calc import ensure_migrations

                ensure_migrations(Path(db_path))
                st.success(t("db_connect.created"))
                db.update_state_after_write(state, db_path)
            except Exception as exc:  # pragma: no cover - UI error path
                st.error(t("errors.failed_create_db", exc=exc))
        return

    schema = db.schema_status(conn)
    if schema["missing_tables"] or schema.get("missing_columns"):
        st.error(t("db_connect.schema_legacy"))
        if schema["missing_tables"]:
            st.write(t("db_connect.missing_tables"))
            st.code(", ".join(schema["missing_tables"]))
        if schema.get("missing_columns"):
            st.write(t("db_connect.missing_columns"))
            for tbl, cols in schema["missing_columns"].items():
                st.code(f"{tbl}: " + ", ".join(cols))
    else:
        st.success(t("db_connect.schema_ok"))

    if schema["has_migrations"]:
        st.write(
            t(
                "db_connect.migrations_list",
                migrations=", ".join(schema.get("migrations") or []),
            )
        )
    else:
        st.warning(t("db_connect.no_migrations_table"))

    if state.get("mode_effective") != "EDIT":
        st.info(t("db_connect.switch_edit"))
        return

    st.subheader(t("db_connect.recreate_header"))
    st.caption(t("db_connect.recreate_caption"))
    confirm_recreate = st.checkbox(t("db_connect.recreate_confirm"))
    if st.button(t("db_connect.recreate_btn"), disabled=not confirm_recreate):
        try:
            from tools.run_calc import (
                ensure_migrations,
                seed_cable_sections_if_empty,
                seed_kr_table_if_empty,
            )

            p = Path(db_path)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = p.with_suffix(p.suffix + f".bak_{ts}")
            shutil.copy2(p, backup)
            p.unlink()
            ensure_migrations(p)
            seed_kr_table_if_empty(p)
            seed_cable_sections_if_empty(p)
            st.success(t("db_connect.recreated", path=str(backup)))
            db.update_state_after_write(state, db_path)
            return
        except Exception as exc:  # pragma: no cover - UI error path
            st.error(t("errors.failed_recreate_db", exc=exc))

    st.subheader(t("db_connect.migrations_header"))
    confirm = st.checkbox(t("db_connect.migrations_confirm"))
    if st.button(t("db_connect.apply_btn"), disabled=not confirm):
        try:
            from tools.run_calc import ensure_migrations

            ensure_migrations(Path(db_path))
            st.success(t("db_connect.migrations_applied"))
            db.update_state_after_write(state, db_path, conn)
        except Exception as exc:  # pragma: no cover - UI error path
            st.error(t("errors.failed_migrations", exc=exc))
