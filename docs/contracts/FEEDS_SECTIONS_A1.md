# FEEDS_SECTIONS_A1

## Goal

A1 separates three concepts and keeps backward compatibility:

- Bus section identity is numeric: `section_no` = `1..N`.
- Incoming supply line is a feed with role: `MAIN | RESERVE | DG | UPS | OTHER`.
- Circuit/consumer binds to bus section; bus section is supplied by one or more feeds.

## Glossary

- `Panel`: electrical panel.
- `BusSection`: section of panel busbars. Identity is `section_no`, optional text label.
- `Feed`: incoming supply line to a panel section.
- `FeedRole`: feed semantic role (`MAIN/RESERVE/DG/UPS/OTHER`).
- `Mode`: calculation scenario (`NORMAL/EMERGENCY`), not a bus-section identity.
- `Consumer`: load connected to panel.
- `Circuit`: outgoing line. Can be bound to a bus section.

## Rules

1. `bus_sections` must have `section_no INTEGER` (`1..N`) and optional `section_label`.
2. `feeds` must have `role` (`MAIN/RESERVE/DG/UPS/OTHER`) and `priority INTEGER` (lower is preferred).
3. A bus section can be linked to multiple feeds via `bus_section_feeds(bus_section_id, feed_id, mode, is_active_default)`.
4. Consumers may have multiple feeds; each feed row has role and priority.
5. `mode` controls which feed roles are active in calculation logic, but `section_no` meaning never changes across modes.
6. Circuit binding uses `circuits.bus_section_id`; section identity is not `MAIN/RESERVE`.

## Backward Compatibility Mapping

- Legacy `consumer_feeds.feed_role='NORMAL'` maps to role `MAIN`.
- Legacy `consumer_feeds.feed_role='RESERVE'` maps to role `RESERVE`.
- Existing `consumer_feeds.priority` is preserved; new `consumer_feeds.feed_priority` is backfilled from it.
- Existing `bus_sections.name='DEFAULT'` gets `section_no=1`.
- Existing unnamed/unindexed sections get `section_no` assigned by stable order: `(name ASC, id ASC)` per panel.
- Existing `section_calc.mode='EMERGENCY'` semantics remain unchanged.
- No legacy columns are dropped in A1.

## DWG Readiness Notes

- `feeds` + `bus_section_feeds` provide explicit topology independent of consumer rows.
- Exports can now represent:
  - section identity (`section_no`)
  - section label (`section_label`)
  - section supply feeds (`role`, `priority`, `mode`)
