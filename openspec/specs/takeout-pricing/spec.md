# Spec: takeout-pricing

> Configurable "para llevar" per-taper surcharge, applied to order totals only for `LLEVAR` orders.

## Requirements

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

## Scenarios

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
