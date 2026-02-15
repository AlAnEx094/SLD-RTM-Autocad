# Streamlit UI Runbook

## Install

```bash
python -m pip install -r requirements.txt
```

## Run

```bash
streamlit run app/streamlit_app.py
```

## QA smoke checklist

- Connect to DB (`db/project.sqlite`) and confirm panel list loads.
- Select a panel, edit one RTM row, Save, then Recalc and Export.
- Verify calc tables are read-only in UI (no direct edits to calc rows).
- TODO: add a UI write-allowlist to assert calc tables are excluded in tests.

## Notes

- Default DB path: `db/project.sqlite` (change in sidebar).
- READ_ONLY is default. Switch to EDIT to modify DB or run calculations.
- If schema is missing tables, apply migrations via the DB Connect page or run:
  `python tools/run_calc.py --db db/project.sqlite --panel-name MVP_PANEL_1`
  (this applies migrations, seeds `kr_table` if empty, and can create demo RTM rows).
