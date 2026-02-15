from __future__ import annotations

from pathlib import Path
import shutil
from datetime import datetime
import streamlit as st

from app import db


def render(conn, state: dict) -> None:
    st.header("DB Connect")

    db_path = state.get("db_path")
    st.write(f"Current DB path: `{db_path}`")

    if not db_path:
        st.error("DB path is empty.")
        return

    if not Path(db_path).exists():
        st.warning("DB file does not exist yet.")
        st.info("Use EDIT mode to create the DB file and apply migrations.")
        if state.get("mode_effective") != "EDIT":
            return

        st.subheader("Create DB + apply migrations")
        confirm = st.checkbox("Create DB file and apply migrations (DDL changes)")
        if st.button("Create DB", disabled=not confirm):
            try:
                from tools.run_calc import ensure_migrations

                ensure_migrations(Path(db_path))
                st.success("DB created and migrations applied.")
                db.update_state_after_write(state, db_path)
            except Exception as exc:  # pragma: no cover - UI error path
                st.error(f"Failed to create DB/apply migrations: {exc}")
        return

    schema = db.schema_status(conn)
    if schema["missing_tables"] or schema.get("missing_columns"):
        st.error(
            "DB schema is incompatible with MVP-UI v0.1. "
            "This DB looks like a legacy schema; migrations may not fix it in-place."
        )
        if schema["missing_tables"]:
            st.write("Missing tables:")
            st.code(", ".join(schema["missing_tables"]))
        if schema.get("missing_columns"):
            st.write("Missing columns:")
            for t, cols in schema["missing_columns"].items():
                st.code(f"{t}: " + ", ".join(cols))
    else:
        st.success("Schema looks complete.")

    if schema["has_migrations"]:
        st.write(f"schema_migrations: {', '.join(schema['migrations'])}")
    else:
        st.warning("schema_migrations table not found.")

    if state.get("mode_effective") != "EDIT":
        st.info("Switch to EDIT mode to apply migrations or recreate DB.")
        return

    st.subheader("Recreate DB (safe)")
    st.caption(
        "Creates a fresh DB at the same path using current migrations. "
        "The existing file will be backed up next to it."
    )
    confirm_recreate = st.checkbox("Backup existing DB and recreate (DESTRUCTIVE)")
    if st.button("Recreate DB", disabled=not confirm_recreate):
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
            st.success(f"DB recreated. Backup: {backup}")
            db.update_state_after_write(state, db_path)
            return
        except Exception as exc:  # pragma: no cover - UI error path
            st.error(f"Failed to recreate DB: {exc}")

    st.subheader("Migrations")
    confirm = st.checkbox("Apply migrations to DB (DDL changes)")
    if st.button("Apply migrations", disabled=not confirm):
        try:
            from tools.run_calc import ensure_migrations

            ensure_migrations(Path(db_path))
            st.success("Migrations applied.")
            db.update_state_after_write(state, db_path, conn)
        except Exception as exc:  # pragma: no cover - UI error path
            st.error(f"Failed to apply migrations: {exc}")
