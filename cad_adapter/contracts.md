# CAD adapter contracts (DB → DWG)

This document defines the integration contracts for a future DWG/AutoCAD rendering layer.

## Core principles

- **DB is the source of truth**.
- **DWG is a render target only** (no calculations, no “fixing” data).
- **Synchronization is one-way**: **DB → DWG**.
- **No AutoCAD API is used in MVP scaffold** (only payload printing).

## Identifiers (GUID)

- **Every block (DWG entity) that represents an object from DB must have a GUID**.
- **`panel_id` corresponds to the GUID of the panel block** in DWG.
- Any nested/child blocks (rows, feeders, labels, etc.) must also have stable GUIDs
  to enable idempotent updates (create/update/delete) during future sync.

## Function contract

### `sync_from_db(db_path: str, panel_id: str) -> None`

Reads calculated results for a given `panel_id` from SQLite and produces a DWG-sync payload.

- **Inputs**:
  - `db_path`: filesystem path to a SQLite database file.
  - `panel_id`: panel identifier (and future panel GUID in DWG).
- **Output**:
  - Returns `None`.
  - Side effects: prints a JSON payload (MVP scaffold).
- **Errors**:
  - May raise exceptions on invalid DB path, SQLite errors, or missing required tables.
  - If calculation rows are missing for `panel_id`, prints a clear message and exits with non-zero
    (script mode).

## Payload (current stub)

The payload is a JSON object with these keys:

- `panel_guid`: equals `panel_id`
- `rtm_panel_calc`: row from `rtm_panel_calc` for `panel_id` (or `null`)
- `panel_phase_calc`: row from `panel_phase_calc` for `panel_id` (or `null`)
- `source_db_path`: as provided

Future versions may extend payload with:

- per-row calculated data (`rtm_row_calc` join `rtm_rows`)
- geometry/layout hints (pure rendering metadata, not calculations)

