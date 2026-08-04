# Design: Menu Combo Sellado

## Technical Approach

Extend the `restaurante` app with a sealed-combo `Menu` (exactly one Entrada + one Segundo at a fixed editable price) and a `Configuracion` singleton holding the "para llevar" per-taper surcharge. Combo lines bill as a unit; taper count is derived from an order's detail lines. Catalog is seeded deterministically by a rewritten `poblar_datos` with `--reset` that soft-deactivates (never deletes) existing rows to coexist with `DetalleOrden.plato`'s `on_delete=PROTECT`. All pricing/surcharge values are admin-editable, never hardcoded. Computed totals move from the POS view into model methods for testability (satisfies `config.yaml` `rules.design`).

## Architecture Decisions

### D1 — Menu model shape
| Option | Tradeoff | Decision |
|---|---|---|
| Explicit M2M plate lists | Restricts pairs, contradicts "any Entrada + any Segundo"; over-constrained | ✗ |
| Generic `MenuItem`/polymorphic line | Over-engineered; no codebase precedent | ✗ |
| **2 FKs to `Categoria` (`categoria_entrada`, `categoria_segundo`)** | Catalog-driven, zero per-plato restriction; category is the eligibility unit per spec | ✓ |

Choose 2 FKs (`on_delete=PROTECT` — a sealed combo must never lose a leg silently). "Any of category A + any of category B" falls out naturally. A detail can be a `Menu` line (composite) or a `Plato` line.

### D2 — Deriving taper count
A taper is a packable **Entrada** or **Segundo**. Terminal rule in a `DetalleOrden.taper_count()`:
- `menu` set → `2 × cantidad`.
- else `plato` whose `categoria.packable` is `True` → `cantidad`.
- else (Añadidos/misc) → `0`.

Packability derives from the category's own `Categoria.packable` flag, NOT from references to active `Menu` rows. This survives zero or a sole-inactive `Menu` row (e.g. seed not run or the single menu deactivated): sopa/segundo a-la-carte lines still price their taper surcharge. `Categoria.packable` defaults to `False` (safe opt-in for newly added, admin-created categories); the seed flags `Entrada`/`Segundo` `packable=True` explicitly and leaves `Añadidos` at `False`. Matches the scenarios (sopa=1, segundo=1, sopa+segundo=2, añadido=0).

### D3 — Configuracion vs site settings
| Option | Tradeoff | Decision |
|---|---|---|
| django-solo / django-constance | New dependency for a monolith; avoid | ✗ |
| Hardcode + fallback | Violates "editable from admin, no code" | ✗ |
| **`Configuracion` singleton row (id=1)** | Native admin, type-safe `DecimalField`, no deps | ✓ |

`Configuracion` holds `recargo_por_taper`. Menu price stays a field on `Menu` (already editable). Singleton enforced via `Configuracion.get()` + admin `has_add_permission=False`.

### D4 — Where the surcharge is computed
| Option | Tradeoff | Decision |
|---|---|---|
| Inline in `pos_view` | Untestable, duplicates CN default total calc | ✗ |
| **Model methods** | Deterministic, unit-testable via `TestCase` | ✓ |

`Orden.computar_total()` = `sum(d.subtotal()) + (2 tapers × recargo)` **only if** `tipo_servicio == 'LLEVAR'`; `MESA` → no surcharge. `pos_view` builds details then sets `orden.total = orden.computar_total()`. Keeps the existing stored `total` DB field contract.

### D5 — `--reset` coexistence with PROTECT
| Option | Decision |
|---|---|
| Hard delete old rows | ✗ breaks PROTECT / destroys history |
| **Soft-deactivate + upsert seed** | ✓ set `activo=False` on non-matching existing catalog rows, then `get_or_create` seed rows and `activo=True` |

Reset never calls `.delete()` on `Categoria`/`Plato`, sidestepping `ProtectedError`. Demo rows with real names (e.g. "Lomo Saltado") are force-set to seed price/`activo=True`; unknown demo rows are deactivated but remain editable/inspectable in admin. Deterministic and idempotent.

## Data Flow

```
POS POST(items, tipo_servicio)
  pos_view ─ per item → DetalleOrden(plato OR menu, precio_unitario, es_para_llevar)
       │
       ▼
  orden.computar_total()          ← metodo: sum subtotals
       │  (tipo_servicio==LLEVAR && tapers>0)  → sum over d.taper_count()
       │                                            × Configuracion.get().recargo_por_taper
       ▼
  orden.total (stored) ──→ reportes / cocina / cobrar (unchanged reads)

--reset seed
  soft-deactivate existing Categoria|Plato → Menu(13) → Configuracion(1)
  upsert seed rows activo=True (get_or_create)
```

## File Changes

| File | Action | Description |
|---|---|---|
| `restaurante/models.py` | Modify | Add `Menu`, `Configuracion`; `DetalleOrden.menu` FK (null=True) + make `plato` nullable |
| `restaurante/migrations/0008_*.py` | Create | New tables + `DetalleOrden.menu`/nullable `plato` |
| `restaurante/admin.py` | Modify | Register `Menu`; `Configuracion` singleton admin; update `DetalleOrdenInline` |
| `restaurante/views.py` | Modify | `pos_view` sets `orden.total = orden.computar_total()` |
| `restaurante/management/commands/poblar_datos.py` | Rewrite | Deterministic seed + `--reset`; keep superuser creation |
| `restaurante/tests.py` | Modify | New combos/extract/surcharge/seed tests |

## Interfaces / Contracts

```python
class Menu(Model):
    nombre = CharField(50)                       # default "Menú"
    precio = DecimalField(8,2)                   # default 13.00
    categoria_entrada = FK(Categoria, PROTECT)
    categoria_segundo = FK(Categoria, PROTECT)
    activo = BooleanField(default=True)

class Configuracion(Model):                      # singleton, id=1
    recargo_por_taper = DecimalField(8,2) default 1.00
    @classmethod
    def get(cls) -> "Configuracion": ...         # ensure id=1

class DetalleOrden(Model):
    plato = FK(Plato, PROTECT, null=True, blank=True)   # nullable now
    menu  = FK(Menu,  PROTECT, null=True, blank=True)   # NEW
    def taper_count(self) -> int: ...
    def subtotal(self) -> Decimal: ...            # unchanged

class Orden(Model):
    def computar_total(self) -> Decimal: ...
```

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit | `taper_count()` (sopa=1, segundo=1, menu=2, añadido=0); `computar_total()` LLEVAR vs MESA; Menu fixed price unit pricing | `TestCase` on model methods |
| Integration | `poblar_datos` exact catalog + determinism; `--reset` idempotent & no `ProtectedError`; `Configuracion.get()` defaults | management command call + assert counts |
| View | `pos_view` POST with menu line + LLEVER applies surcharge, MESA doesn't | Django `Client` + persisted `Orden.total` |
| Admin | Menu + Configurcación enregistrable / editable | `admin.ModelAdmin` registration smoke |

Command: `DATABASE_URL=sqlite:///./db.sqlite3 python manage.py test` (must prefix to avoid remote Neon).

## Migration / Rollout

`makemigrations restaurante` (0008) creates `Menu` + `Configuracion`, adds nullable `DetalleOrden.menu`, and makes `plato` nullable. Backwards-compatible (new nullable fields), no data backfill. Apply locally on SQLite for tests use; remote Neon apply follows existing governance and should be `Timeout` avoid breaking running orders. `--reset` is safe to re-run (idempotent, no delete).

## Open Questions

- [x] Confirm exactly one seeded `Menu` (name "Menú"). Note: `Menu` is no longer the anchor for taper packability — packability is now an intrinsic `Categoria.packable` flag (see D2). Multiple menus remain out of scope.
- [ ] Whether `es_para_llevar` per-detail should gate taper counting in addition to order `tipo_servicio=LLEVAR`, or order-level suffices (spec implies order-level). Resolve in tasks/apply.
- [ ] `Nota`: current `pos_view` bills both `tipo_servicio` and per-detail `es_para_llevar`; confirm these stay in sync.