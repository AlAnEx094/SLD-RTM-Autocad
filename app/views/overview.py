from __future__ import annotations

import streamlit as st

from app import db
from app.i18n import t


def render(conn, state: dict) -> None:
    st.header(t("overview.header"))
    counts = db.project_counts(conn)
    cols = st.columns(4)
    cols[0].metric(t("overview.panels"), counts["panels"])
    cols[1].metric(t("overview.rtm_rows"), counts["rtm_rows"])
    cols[2].metric(t("overview.circuits"), counts["circuits"])
    cols[3].metric(t("overview.consumers"), counts["consumers"])
