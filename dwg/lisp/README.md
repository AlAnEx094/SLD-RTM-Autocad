# DWG LISP Scripts — MVP-0.6

AutoLISP utilities for importing attribute values from CSV into DWG block references.

## IMPORT_ATTRS

Command to import CSV attribute values into block references by GUID.

### How to load and run

1. **APPLOAD** the script in AutoCAD:
   - Type `APPLOAD` (or `Tools` → `Load Application`)
   - Browse to `dwg/lisp/import_attrs.lsp`
   - Click **Load** (optionally check "Add to Startup Suite" for auto-load)

2. **Run the command**:
   - Type `IMPORT_ATTRS` at the command line
   - When prompted, enter the folder path containing the CSV files

### Expected CSV location and format

**Path input:** The command prompts for a **directory path**. The script expects these three files in that directory:

- `attrs_panel.csv`
- `attrs_circuits.csv`
- `attrs_sections.csv`

**Examples:**
- `out/` or `out` → looks for `out/attrs_panel.csv`, etc.
- `C:/project/out` or `C:/project/out/` → same
- Relative paths are relative to the current drawing’s path or AutoCAD working directory

**CSV formats:**

| File                | Header        | Columns                    |
|---------------------|---------------|----------------------------|
| attrs_panel.csv     | GUID,ATTR,VALUE | GUID, attribute name, value |
| attrs_circuits.csv  | GUID,ATTR,VALUE | GUID, attribute name, value |
| attrs_sections.csv  | GUID,MODE,ATTR,VALUE | GUID, mode, attribute name, value |

- First row is a header and is skipped.
- `GUID` — block attribute value used to match blocks in the drawing.
- `ATTR` — name of the block attribute to update.
- `VALUE` — value to write.
- `MODE` — used for section blocks (e.g. NORMAL, RESERVE); must match the block’s MODE attribute.

### Behavior

- Updates **existing** attributes only; does not create new attributes.
- Never modifies the GUID attribute.
- Block name is irrelevant; matching is by GUID only.
- Section blocks must have a MODE attribute; values are applied per GUID+MODE.

### Summary output

After execution, the command prints:

- `blocks_scanned` — total INSERT entities processed
- `blocks_with_guid` — blocks that had a non-empty GUID attribute
- `updated_attrs_count` — number of attributes updated
- `blocks_skipped_no_guid` — blocks without attributes or without GUID
- `guid_not_found_in_csv` — blocks whose GUID was not found in any CSV

### Known limitations

1. **CSV parsing:** Values must not contain commas. Quoted fields with embedded commas are not supported.
2. **Encoding:** Files are read as plain text; UTF-8 is recommended.
3. **Path format:** Use forward slashes (`/`) or backslashes (`\`) as appropriate for the OS; AutoCAD accepts both on Windows.
