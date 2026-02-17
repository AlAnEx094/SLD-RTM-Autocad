-- 0010_circuits_bus_section.sql
-- MVP-BAL v0.3a: bind circuits to bus sections.
-- Idempotent: ADD COLUMN is not idempotent in SQLite
-- (migration relies on schema_migrations to run once).

PRAGMA foreign_keys = ON;

-- circuits.bus_section_id: optional FK to bus_sections (circuit may be unbound)
-- ON DELETE SET NULL: when bus_section is deleted, circuit becomes unbound (not deleted)
ALTER TABLE circuits ADD COLUMN bus_section_id TEXT NULL REFERENCES bus_sections(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_circuits_bus_section_id ON circuits(bus_section_id);
