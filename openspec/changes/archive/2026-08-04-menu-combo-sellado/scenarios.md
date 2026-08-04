# Scenarios — Menu Combo Sellado

Acceptance and test scenarios per requirement. All scenarios are written so an `sdd-apply` executor can verify each with a Django `TestCase`.

## menu-combo

### Requirement: Menu sealed-combo entity

#### Scenario: Create a sealed combo with fixed price
- GIVEN a Menu is created with name "Menú" and price 13.00 S/, wired to the Entrada and Segundo categories
- WHEN the Menu is saved
- THEN it persists with `precio=13.00`, `activo=True`, and `nombre="Menú"`
- AND both the Entrada and Segundo categories are recorded as its eligible catalogs

#### Scenario: Any entrada with any segundo is accepted
- GIVEN the Entrada category contains Sopa de Res and the Segundo category contains Lomo Saltado and Chuleta de Chancho
- WHEN a Menu references both categories
- THEN any pairing (e.g. Sopa de Res + Lomo Saltado, or Sopa de Res + Chuleta de Chancho) is valid with no per-plato restriction

#### Scenario: Menu price is admin-editable
- GIVEN a Menu with `precio=13.00`
- WHEN an admin edits the price to 15.00 S/ (no code change)
- THEN the stored price becomes 15.00 and the new value is used for pricing

#### Scenario: Inactive menu is unavailable
- GIVEN a Menu with `activo=False`
- WHEN availability is queried
- THEN the Menu is excluded from selectable options

### Requirement: Menu pricing as a unit

#### Scenario: Order line prices at the fixed menu price
- GIVEN an order line refers to the Menu (price 13.00) rather than its constituent platos
- WHEN the line subtotal is computed
- THEN it equals `cantidad × 13.00`, not the sum of the sopa + segundo prices

#### Scenario: Menu + añadidos sum without taper penalty
- GIVEN a LLEVAR order with one Menu and one Huevo (1.50 S/)
- WHEN the total is computed
- THEN the total is `13.00 + 1.50 + (2 × surcharge)` for the two tapers (sopa + segundo), and the añadido adds only price

## takeout-pricing

### Requirement: Configurable per-taper surcharge

#### Scenario: Default surcharge is seeded
- GIVEN fresh seed
- WHEN surcharge config is read
- THEN `recargo_por_taper` equals 1.00 S/

#### Scenario: Surcharge is admin-editable
- GIVEN a seeded surcharge of 1.00 S/
- WHEN an admin changes it to 2.00 S/
- THEN subsequent LLEVAR totals use 2.00 S/ per taper

### Requirement: Taper counting for LLEVAR orders

#### Scenario: Solo sopa counts one taper
- GIVEN a LLEVAR order containing only Sopa de Res
- WHEN taper count is computed
- THEN it equals 1

#### Scenario: Solo segundo counts one taper
- GIVEN a LLEVAR order containing only Lomo Saltado
- WHEN taper count is computed
- THEN it equals 1

#### Scenario: Sopa + segundo counts two tapers
- GIVEN a LLEVAR order containing Sopa de Res and Lomo Saltado
- WHEN taper count is computed
- THEN it equals 2

#### Scenario: Añadidos do not add tapers
- GIVEN a LLEVAR order with one Huevo and one Porción de Papa and no sopa or segundo
- WHEN taper count is computed
- THEN it equals 0, and only the añadido prices are added to the total

### Requirement: Surcharge applied only to LLEVAR

#### Scenario: LLEVAR order total includes surcharge
- GIVEN a LLEVAR order with one Menu (sopa+segundo = 2 tapers) at 13.00 S/
- WHEN the total is computed
- THEN it equals `13.00 + (2 × 1.00) = 15.00`

#### Scenario: MESA order total has no surcharge
- GIVEN a MESA order with the same items
- WHEN the total is computed
- THEN it equals the sum of plato prices with no taper surcharge added

## catalog-management

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
