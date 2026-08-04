# Proposal: Menu Combo Sellado

## Intent

Current catalog is demo/placeholder data (e.g. "Ceviche Mixto", "Arroz con Pollo") that does
not match the real restaurant and lacks a sealed combo product. The owner needs a market-fitting
catalog plus a **Menú** (combo sellado: 1 Entrada + 1 Segundo, single fixed price) and
configurable takeout surcharges. All catalog data must be admin-editable, never hardcoded.

## Scope

### In Scope
- New `Menu` entity (entrada + segundo combo), fixed editable price (13 S/ default, may rise to 15).
- Combo accepts ANY Entrada + ANY Segundo (no restriction).
- Replace current catalog with seeded catalog: Entradas, 10 Segundos (11 S/ each), Añadidos (Huevo 1.50, Arroz 3, Papa 3).
- Seed/repopulate command to reset to initial state.
- Configurable takeout surcharge per taper (sopa +1, menú/sopa+segundo +2).
- Admin editability for categories, platos, menú, and surcharge.
- Migration for new `Menu` table (+ any `DetalleOrden`/pricing adjustments).

### Out of Scope
- Customer-facing ordering UI redesign (POS continues using existing views).
- Full billing/invoice generation.
- Menu item markup-upselling, combos beyond entrada+segundo.

## Capabilities

> No specs exist yet (`openspec/specs/` empty). All are new capabilities.

### New Capabilities
- `menu-combo`: `Menu` entity — sealed entrada+segundo offering, editable fixed price, active flag, eligible category wiring.
- `takeout-pricing`: configurable per-taper "para llevar" surcharge applied to order totals.
- `catalog-management`: full admin editability of Categoria/Plato/Menu + seed/repopulate command.

### Modified Capabilities
- None (no prior specs).

## Approach

Add `Menu` model (~ PLAT pricing pattern of `Plato`) with M2M/FK to eligible categories.
Introduce a `Configuracion` (or setting row) for takeout per-taper amounts so surcharges are
admin-edited. Replace `poblar_datos.py` contents with a deterministic seed of the real catalog and
a `--reset` mode that clears existing rows first. Wire surcharge into `pos_view` total calc.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `restaurante/models.py` | Modified | Add `Menu`; possibly `Configuracion`; adjust `DetalleOrden` for combo type |
| `restaurante/migrations/*` | New | Migration for `Menu` + any pricing fields |
| `restaurante/admin.py` | Modified | Register `Menu`; expose surcharge config |
| `restaurante/management/commands/poblar_datos.py` | Modified | New seed catalog + reset mode |
| `restaurante/views.py` | Modified | `pos_view` applies takeout surcharge to totals |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Deleting current catalog breaks existing orders (FK depend) | Med | Soft-deactivate or guard deletes with ProtectedError (existing pattern); seed only where safe |
| Surcharge rule ambiguity (segundo solo, añadidos/taper) | High | Track as open questions; configure defaults, revisit in design before hardcoding |
| Neon remote DB migration divergence | Med | Test migrations on local SQLite; follow config.governance for remote apply |

## Rollback Plan

Reverse migration for `Menu`/pricing; re-run prior `poblar_datos` to restore demo catalog.
Keep old catalog rows soft-deactivated rather than hard-deleted where orders reference them.

## Dependencies

- Django admin already configured (Categoria/Plato exist).
- DB migration runnable on both SQLite (local) and Neon (remote).

## Success Criteria

- [ ] `Menu` combo can be created/edited/price-adjusted from admin without code changes.
- [ ] Takeout surcharge amounts editable from admin and applied to order totals.
- [ ] Seed command restores exact initial catalog after `--reset`.
- [ ] Existing test suite (`manage.py test`) still passes; new tests cover combo + surcharge.

## Open Questions (resolve in design/spec — non-blocking)

- Sopa a la carta/takeout: surcharge basis and taper count for *sopa sola* vs *sopa+segundo*.
- Segundos "para llevar" solo (no sopa): does one taper = +1 S/ still apply?
- Do Añadidos count toward taper count / surcharge?
- Does surcharge apply only to `LLEVAR` orders, not `MESA`?