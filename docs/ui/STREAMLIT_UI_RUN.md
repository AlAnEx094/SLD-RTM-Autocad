# Streamlit UI Runbook

## Install

```bash
python -m pip install -r requirements.txt
```

## Run

```bash
streamlit run app/streamlit_app.py
```

## Notes

- Default DB path: `db/project.sqlite` (change in sidebar).
- READ_ONLY is default. Switch to EDIT to modify DB or run calculations.
- If schema is missing tables, apply migrations via the DB Connect page or run:
  `python tools/run_calc.py --db db/project.sqlite --panel-name MVP_PANEL_1`
  (this applies migrations, seeds `kr_table` if empty, and can create demo RTM rows).
