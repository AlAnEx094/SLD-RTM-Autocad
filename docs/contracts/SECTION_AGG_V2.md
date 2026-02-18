# SECTION_AGG_V2 — Aggregation by bus sections (Feeds v2)

## Scope

This contract describes how `calc_core.section_aggregation` aggregates consumer loads into `section_calc`
for **calculation modes** `NORMAL` / `EMERGENCY` (Feeds v2).

## Glossary (RU/EN)

- **Щит / Panel**: `panels`
- **Секция шин / Bus section**: `bus_sections`
- **Потребитель / Consumer**: `consumers`
- **Ввод / Feed**: one row in `consumer_feeds`
- **Роль ввода / Feed role**: `feed_roles` (`MAIN/RESERVE/DG/UPS/OTHER`; legacy `DC` is compatibility-only)
- **Режим расчёта / Calculation mode**: `modes` (`NORMAL/EMERGENCY`)

## DB tables (inputs)

- `consumers(id, panel_id, load_ref_type, load_ref_id, p_kw, q_kvar, s_kva, i_a, ...)`
- `consumer_feeds(consumer_id, bus_section_id, feed_role_id, priority, ...)`
- `consumer_mode_rules(consumer_id, mode_id, active_feed_role_id)`
- `rtm_panel_calc(panel_id, pp_kw, qp_kvar, sp_kva, ip_a, ...)` (when consumer is `RTM_PANEL`)
- `bus_sections(id, panel_id, name)`

## Output table (persisted)

`section_calc(panel_id, bus_section_id, mode, p_kw, q_kvar, s_kva, i_a, updated_at)`

Where `mode` is the **calculation mode**:

- `NORMAL`
- `EMERGENCY`

## Algorithm (normative)

For a given `panel_id` and requested `mode`:

For each consumer `c` in `consumers` where `c.panel_id = panel_id`:

1) Determine `active_role` (feed role id):
   - If a row exists in `consumer_mode_rules` for `(consumer_id=c.id, mode_id=mode)`:
     - `active_role = consumer_mode_rules.active_feed_role_id`
   - Else use defaults:
     - `NORMAL` → `MAIN`
     - `EMERGENCY` → `RESERVE`

2) Select the active feed row:
   - Find rows in `consumer_feeds` with:
     - `consumer_id = c.id`
     - `feed_role_id = active_role`
   - If multiple rows match, choose the one with the **minimum `priority`**.
     - Tie-breaker: stable order by feed id (implementation detail).

3) Determine `bus_section_id` from the selected feed row.

4) Determine consumer load:
   - If `c.load_ref_type = 'RTM_PANEL'`:
     - read `(pp_kw, qp_kvar, sp_kva, ip_a)` from `rtm_panel_calc` for `panel_id = c.load_ref_id`
   - If `c.load_ref_type = 'MANUAL'`:
     - read `(p_kw, q_kvar, s_kva, i_a)` from `consumers` row
   - `RTM_ROW` is currently not supported.

5) Add the load to the accumulator for `(bus_section_id, mode)`.

After processing all consumers:

- Upsert one row per bus section into `section_calc` for `(panel_id, bus_section_id, mode)`.

## Fallbacks (implementation requirement)

If no feed exists for the selected `active_role`:

- First fallback: try `MAIN` role (if present).
- Final fallback: choose **any** available feed for the consumer with minimal `priority`.
- If consumer has no feeds at all: skip the consumer and emit a warning.

## Compatibility notes (transition period)

The code supports a transition where older UI/DB may still use legacy mode names:

- In Feeds v2 DB: `RESERVE` is treated as a deprecated alias of `EMERGENCY`.
- In legacy DB (Feeds v1): `EMERGENCY` is treated as a deprecated alias of `RESERVE`.

These aliases are **compatibility only** and should be removed once UI/exports are fully migrated.

