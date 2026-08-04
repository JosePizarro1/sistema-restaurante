# Requirements — Menu Combo Sellado

Delta spec for change `menu-combo-sellado`. No prior specs exist (`openspec/specs/` empty), so all requirements are ADDED.

## ADDED Requirements — menu-combo

### Requirement: Menu sealed-combo entity

The system MUST provide a `Menu` entity representing a sealed combo of exactly one Entrada (sopa) + one Segundo, sold at a single fixed price independent of the chosen platos.

- The system MUST store the combo price as an editable field (default 13.00 S/) and MUST NOT hardcode it.
- The system MUST include an active flag controlling availability.
- The system MUST accept ANY Entrada + ANY Segundo from the full eligible categories, with no per-plato restriction.
- The system MUST persist the combo name (default "Menú").
- The system SHALL wire the Menu to the Entrada and Segundo categories as the eligible catalogs.

### Requirement: Menu pricing as a unit

The system MUST price an order line for a Menu at the Menu's fixed price, not the sum of its constituent platos.

## ADDED Requirements — takeout-pricing

### Requirement: Configurable per-taper surcharge

The system MUST expose an editable configuration value for the "para llevar" surcharge per taper (default 1.00 S/), editable from admin without code changes.

### Requirement: Taper counting for LLEVAR orders

For orders with `tipo_servicio=LLEVAR`, the system MUST count packable items (Entrada/sopa and Segundo only) to derive taper count:

- Solo sopa → 1 taper.
- Solo segundo → 1 taper.
- Sopa + segundo → 2 tapers.
- Añadidos MUST NOT count toward tapers (they only add their price).

### Requirement: Surcharge applied only to LLEVAR

The system MUST add `taper_count × recargo_por_taper` to the order total ONLY for `tipo_servicio=LLEVAR`. The system MUST NOT apply any surcharge to `tipo_servicio=MESA`.

## ADDED Requirements — catalog-management

### Requirement: Real seeded catalog

The system MUST replace placeholder catalog data with a deterministic seed:

- Entrada: Sopa de Res (6.00 S/).
- Segundos (11.00 S/ each): Lomo Saltado, Pollo Dorado, Hamburguesa al Plato, Chuleta de Res, Saltado de Mollejas, Hígado Frito, Pollo Broaster, Riñón Saltado, Chuleta de Chancho, Arroz a la Cubana.
- Añadidos: Huevo (1.50 S/), Porción de Arroz (3.00 S/), Porción de Papa (3.00 S/).

### Requirement: Seed command with reset mode

The system MUST provide a `poblar_datos` command that repopulates the initial catalog, Menu (13.00 S/), and surcharge config (1.00 S/) deterministically. With a `--reset` flag, the command MUST first clear existing catalog/config rows, then seed.

### Requirement: Full admin editability

The system MUST allow editing Categoria, Plato, Menu, and surcharge configuration entirely from Django admin, without code changes.
