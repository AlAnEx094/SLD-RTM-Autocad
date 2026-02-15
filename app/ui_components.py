from __future__ import annotations

from dataclasses import asdict
from typing import Any

import streamlit as st

from app.db import StatusInfo


def _status_style(status: str) -> tuple[str, str]:
    """
    Returns (bg_color, fg_color) for a status pill.
    Colors are chosen to be readable in both Streamlit light/dark themes.
    """
    s = (status or "").upper().strip()
    if s == "OK":
        return "#1f7a3a", "white"
    if s == "STALE":
        return "#b45309", "white"
    if s == "UNKNOWN":
        return "#b7791f", "white"
    if s == "NO_CALC":
        return "#b91c1c", "white"
    if s == "HIDDEN":
        return "#6b7280", "white"
    return "#374151", "white"


def _details_text(info: StatusInfo) -> str:
    parts: list[str] = [f"status={info.status}"]
    if info.reason:
        parts.append(f"reason={info.reason}")
    if info.effective_input_at:
        parts.append(f"effective_input_at={info.effective_input_at}")
    if info.calc_updated_at:
        parts.append(f"calc_updated_at={info.calc_updated_at}")
    return "; ".join(parts)


def status_chip(label: str, info: StatusInfo, *, show_details: bool = True) -> None:
    """
    Compact status chip with optional details popover.
    Matches SPEC wording for codes: OK/STALE/NO_CALC/UNKNOWN.
    """
    if info.status == "HIDDEN":
        return

    bg, fg = _status_style(info.status)
    title = _details_text(info).replace('"', "'")

    cols = st.columns([0, 1], vertical_alignment="center")
    with cols[0]:
        st.markdown(
            f"""
            <span title="{title}" style="
              display:inline-block;
              padding:0.15rem 0.55rem;
              border-radius:999px;
              background:{bg};
              color:{fg};
              font-weight:600;
              font-size:0.85rem;
              line-height:1.4;
              white-space:nowrap;
            ">{label}: {info.status}</span>
            """,
            unsafe_allow_html=True,
        )
    with cols[1]:
        if show_details:
            with st.popover("Details"):
                st.json(asdict(info))  # stable shape for debugging

