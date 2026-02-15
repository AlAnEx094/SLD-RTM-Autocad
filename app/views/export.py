from __future__ import annotations

import csv
import json
from pathlib import Path
import streamlit as st

from app import db


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def render(conn, state: dict) -> None:
    st.header("Export")

    panel_id = state.get("selected_panel_id")
    if not panel_id:
        st.info("Select a panel to export.")
        return

    rtm_info = db.rtm_status(conn, panel_id, external_change=state.get("external_change", False))
    if rtm_info.status != "OK":
        st.error(f"RTM status is {rtm_info.status}. Export is blocked by default.")
        with st.popover("Why?"):
            st.write(f"status: `{rtm_info.status}`")
            if rtm_info.reason:
                st.write(f"reason: `{rtm_info.reason}`")
            if rtm_info.calc_updated_at:
                st.write(f"calc_updated_at: `{rtm_info.calc_updated_at}`")
            if rtm_info.effective_input_at:
                st.write(f"effective_input_at: `{rtm_info.effective_input_at}`")
        allow = st.checkbox("Export despite non-OK RTM status (not recommended)")
        if not allow:
            return

    st.subheader("JSON payload (v0.4)")
    default_json = Path("out") / f"payload_{panel_id[:8]}.json"
    out_json = st.text_input("Output JSON path", value=str(default_json))
    if st.button("Export JSON payload"):
        try:
            from calc_core.export_payload import build_payload

            ro_conn = db.connect(state["db_path"], read_only=True)
            try:
                payload = build_payload(ro_conn, panel_id)
            finally:
                ro_conn.close()
            out_path = Path(out_json)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            st.success(f"JSON exported: {out_path}")
            st.download_button(
                "Download JSON",
                data=out_path.read_bytes(),
                file_name=out_path.name,
            )
        except Exception as exc:  # pragma: no cover - UI error path
            st.error(f"Export failed: {exc}")

    st.subheader("CSV attributes (v0.5)")
    mapping_path = st.text_input(
        "Mapping path", value=str(Path("dwg") / "mapping_v0_5.yaml")
    )
    out_dir = st.text_input("Output directory", value="out")

    st.write("Files to be generated: attrs_panel.csv, attrs_circuits.csv, attrs_sections.csv")

    if st.button("Export CSV attributes"):
        try:
            from calc_core.export_attributes_csv import (
                build_rows_from_payload,
                load_mapping,
            )
            from calc_core.export_payload import build_payload

            ro_conn = db.connect(state["db_path"], read_only=True)
            try:
                payload = build_payload(ro_conn, panel_id)
            finally:
                ro_conn.close()

            mapping = load_mapping(mapping_path)
            rows = build_rows_from_payload(payload, mapping)
            out_dir_path = Path(out_dir)
            _write_csv(
                out_dir_path / "attrs_panel.csv",
                ["GUID", "ATTR", "VALUE"],
                rows["panel"],
            )
            _write_csv(
                out_dir_path / "attrs_circuits.csv",
                ["GUID", "ATTR", "VALUE"],
                rows["circuits"],
            )
            _write_csv(
                out_dir_path / "attrs_sections.csv",
                ["GUID", "MODE", "ATTR", "VALUE"],
                rows["sections"],
            )

            st.success(f"CSV exported to: {out_dir_path}")
            st.write(
                f"Rows: panel={len(rows['panel'])}, circuits={len(rows['circuits'])}, sections={len(rows['sections'])}"
            )
            for filename in ("attrs_panel.csv", "attrs_circuits.csv", "attrs_sections.csv"):
                file_path = out_dir_path / filename
                if file_path.exists():
                    st.download_button(
                        f"Download {filename}",
                        data=file_path.read_bytes(),
                        file_name=filename,
                    )
        except Exception as exc:  # pragma: no cover - UI error path
            st.error(f"Export failed: {exc}")
