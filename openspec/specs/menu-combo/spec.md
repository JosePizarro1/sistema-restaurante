# Spec: menu-combo

> Sealed "Menú" combo (exactly one Entrada + one Segundo) sold at a single fixed editable price, independent of the chosen platos.

## Requirements

### Requirement: Menu sealed-combo entity

The system MUST provide a `Menu` entity representing a sealed combo of exactly one Entrada (sopa) + one Segundo, sold at a single fixed price independent of the chosen platos.

- The system MUST store the combo price as an editable field (default 13.00 S/) and MUST NOT hardcode it.
- The system MUST include an active flag controlling availability.
- The system MUST accept ANY Entrada + ANY Segundo from the full eligible categories, with no per-plato restriction.
- The system MUST persist the combo name (default "Menú").
- The system SHALL wire the Menu to the Entrada and Segundo categories as the eligible catalogs.

### Requirement: Menu pricing as a unit

The system MUST price an order line for a Menu at the Menu's fixed price, not the sum of its constituent platos.

## Scenarios

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
