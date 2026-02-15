from __future__ import annotations

from pathlib import Path
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
    if schema["missing_tables"]:
        st.error(
            "Missing tables: "
            + ", ".join(schema["missing_tables"])
            + ". Run migrations/bootstrap."
        )
    else:
        st.success("Schema looks complete.")

    if schema["has_migrations"]:
        st.write(f"schema_migrations: {', '.join(schema['migrations'])}")
    else:
        st.warning("schema_migrations table not found.")

    if state.get("mode_effective") != "EDIT":
        st.info("Switch to EDIT mode to apply migrations.")
        return

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
