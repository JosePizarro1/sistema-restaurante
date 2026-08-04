# Spec: catalog-management

> Deterministic seeded real catalog, a `poblar_datos` seed command with `--reset`, and full admin editability of all catalog entities.

## Requirements

### Requirement: Real seeded catalog

The system MUST replace placeholder catalog data with a deterministic seed:

- Entrada: Sopa de Res (6.00 S/).
- Segundos (11.00 S/ each): Lomo Saltado, Pollo Dorado, Hamburguesa al Plato, Chuleta de Res, Saltado de Mollejas, Hígado Frito, Pollo Broaster, Riñón Saltado, Chuleta de Chancho, Arroz a la Cubana.
- Añadidos: Huevo (1.50 S/), Porción de Arroz (3.00 S/), Porción de Papa (3.00 S/).

### Requirement: Seed command with reset mode

The system MUST provide a `poblar_datos` command that repopulates the initial catalog, Menu (13.00 S/), and surcharge config (1.00 S/) deterministically. With a `--reset` flag, the command MUST first clear existing catalog/config rows, then seed.

### Requirement: Full admin editability

The system MUST allow editing Categoria, Plato, Menu, and surcharge configuration entirely from Django admin, without code changes.

## Scenarios

### Requirement: Real seeded catalog

#### Scenario: Seed creates the exact catalog
- GIVEN an empty database
- WHEN the seed command runs
- THEN exactly 1 Entrada (Sopa de Res, 6.00), 10 Segundos (11.00 each), and 3 Añadidos (Huevo 1.50, Arroz 3.00, Papa 3.00) exist

#### Scenario: Seed is deterministic
- GIVEN an empty database
- WHEN the seed command runs twice
- THEN the resulting catalog is identical in both runs

### Requirement: Seed command with reset mode

#### Scenario: Reset clears then reseeds
- GIVEN a database with modified catalog and config rows
- WHEN the seed command runs with `--reset`
- THEN existing rows are cleared and the exact initial catalog, Menu (13.00), and surcharge (1.00) are restored

#### Scenario: Reset is idempotent
- GIVEN a seeded database
- WHEN the seed command runs twice with `--reset`
- THEN no duplicate catalog rows are created and the final state matches the initial seed

### Requirement: Full admin editability

#### Scenario: Admin can manage all catalog entities
- GIVEN a superuser session
- WHEN creating/editing a Categoria, Plato, Menu, or the surcharge config
- THEN the change persists via the admin interface without code changes
