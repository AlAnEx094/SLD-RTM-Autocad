# FEEDS_SECTIONS_A1 — Domain contract (A1)

## 1) Glossary

- **Panel** — electrical panel.
- **BusSection** — bus section inside a panel.
- **Feed** — incoming supply line/source that can supply a panel/bus section.
- **FeedRole** — role/type of a feed: `MAIN` / `RESERVE` / `DG` / `UPS` / `OTHER`.
- **Mode** — calculation scenario: `NORMAL` / `EMERGENCY`.
- **Consumer** — load bound to a parent panel.
- **Circuit** — outgoing circuit/line from a panel.

## 2) Core model rules

1. **BusSection identity is numeric**
   - `bus_sections.section_no` is integer `1..N` and is the stable section identity.
   - Optional human label is stored separately (`section_label`), and legacy `name` remains for compatibility.
   - `section_no` **never** means MAIN/RESERVE and does not depend on mode.

2. **Feed identity is role + priority (not section semantics)**
   - `feeds.role` is `MAIN | RESERVE | DG | UPS | OTHER`.
   - `feeds.priority` is integer (`lower => preferred`).
   - Model supports more than two feeds per panel.

3. **Consumer topology**
   - Consumer may have multiple candidate feeds (`consumer_feeds`) with own role and priority.
   - Consumer feed row always references a **bus section** (`consumer_feeds.bus_section_id`).

4. **Bus section supply topology (explicit for DWG future)**
   - A bus section can be supplied by one or more feeds via `bus_section_feeds(bus_section_id, feed_id, mode, is_active_default)`.
   - This relation is explicit and independent from per-consumer mapping.

5. **Mode semantics**
   - `Mode` selects which feed roles are considered active in calculations/rules.
   - `Mode` does **not** rename/redefine bus sections.
   - Section semantics remain numeric (`section_no`) across all modes.

## 3) Backward compatibility mapping

- Legacy `consumer_feeds.feed_role` (`NORMAL`/`RESERVE`) remains untouched and is treated as deprecated compatibility input.
- New/primary role dimension uses `feed_role_id` + `feed_priority`.
- Legacy bus section name (`DEFAULT`) is mapped to `section_no=1` during migration.
- Existing `section_calc.mode` migration (`RESERVE -> EMERGENCY`) remains valid and independent from `section_no`.
- Existing feed role dictionary remains valid; `OTHER` is added without removing legacy roles/codes.

## 4) Deterministic data migration rules (A1)

- `bus_sections.section_no` backfill:
  - if panel has `DEFAULT` section, it gets `section_no=1` by ordering rule,
  - other missing numbers are assigned by deterministic ordering inside panel (`DEFAULT` first, then name/id).
- `feeds` backfill from existing `consumer_feeds`:
  - deduplicate by `(panel_id, role)` and use minimal priority.
- `bus_section_feeds` backfill:
  - derive section-feed links from existing consumer feed usage and mode rules/default mode-role mapping.

## 5) A1 scope note

A1 introduces domain separation and DB/UI support; advanced runtime switching of active section feeds is reserved for later increments (A2+).
