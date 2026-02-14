# CAD adapter (MVP scaffold)

This module is an **integration scaffold** between the SQLite database (source of truth)
and a future **DWG/AutoCAD rendering layer**.

## Scope (current)

- **DB → DWG only** (one-way sync).
- **No AutoCAD API integration** yet (printing a payload stub instead).
- Reads calculated results from:
  - `rtm_panel_calc`
  - `panel_phase_calc`

## Non-goals (current)

- No changes to `calc_core/`
- No changes to `db/` schema/migrations/seeds
- No drawing/creating DWG entities

## Usage

Run as a script:

```bash
python cad_adapter/dwg_sync.py --db db/project.sqlite --panel-id <PANEL_ID>
```

Or import the function:

```python
from cad_adapter.dwg_sync import sync_from_db

sync_from_db(db_path="db/project.sqlite", panel_id="PANEL_001")
```

## What it prints

The script prints a JSON payload representing **what would be sent to DWG** later:

- Panel GUID (equals `panel_id`)
- RTM panel totals (`rtm_panel_calc`)
- Phase balance totals (`panel_phase_calc`)

