from __future__ import annotations

import csv
import json
from pathlib import Path
import streamlit as st

from app import db
from app.i18n import t
from app.ui_components import status_chip


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def render(conn, state: dict) -> None:
    st.header(t("export.header"))

    panel_id = state.get("selected_panel_id")
    if not panel_id:
        st.info(t("export.select_panel"))
        return

    rtm_info = db.rtm_status(conn, panel_id, external_change=state.get("external_change", False))
    if rtm_info.status != "OK":
        status_chip("RTM", rtm_info, t=t)
        st.error(t("export.blocked"))
        allow = st.checkbox(t("export.allow_anyway"))
        if not allow:
            return
    else:
        status_chip("RTM", rtm_info, t=t)

    st.subheader(t("export.json_header"))
    default_json = Path("out") / f"payload_{panel_id[:8]}.json"
    out_json = st.text_input(t("export.output_json"), value=str(default_json))
    if st.button(t("export.json_btn")):
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
            st.success(t("export.json_exported", path=str(out_path)))
            st.download_button(
                t("export.download_json"),
                data=out_path.read_bytes(),
                file_name=out_path.name,
            )
        except Exception as exc:  # pragma: no cover - UI error path
            st.error(t("errors.export_failed", exc=exc))

    st.subheader(t("export.csv_header"))
    mapping_path = st.text_input(
        t("export.mapping_path"), value=str(Path("dwg") / "mapping_v0_5.yaml")
    )
    out_dir = st.text_input(t("export.output_dir"), value="out")

    st.write(t("export.files_info"))

    if st.button(t("export.csv_btn")):
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

            st.success(t("export.csv_exported", path=str(out_dir_path)))
            st.write(
                t(
                    "export.rows_info",
                    panel=len(rows["panel"]),
                    circuits=len(rows["circuits"]),
                    sections=len(rows["sections"]),
                )
            )
            for filename in ("attrs_panel.csv", "attrs_circuits.csv", "attrs_sections.csv"):
                file_path = out_dir_path / filename
                if file_path.exists():
                    st.download_button(
                        t("export.download_file", filename=filename),
                        data=file_path.read_bytes(),
                        file_name=filename,
                    )
        except Exception as exc:  # pragma: no cover - UI error path
            st.error(t("errors.export_failed", exc=exc))
