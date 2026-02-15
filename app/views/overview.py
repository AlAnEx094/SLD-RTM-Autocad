from __future__ import annotations

import streamlit as st

from app import db


def render(conn, state: dict) -> None:
    st.header("Project Overview")
    counts = db.project_counts(conn)
    cols = st.columns(4)
    cols[0].metric("Panels", counts["panels"])
    cols[1].metric("RTM rows", counts["rtm_rows"])
    cols[2].metric("Circuits", counts["circuits"])
    cols[3].metric("Consumers", counts["consumers"])
