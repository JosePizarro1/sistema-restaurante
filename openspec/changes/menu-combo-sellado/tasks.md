# Tasks: Menu Combo Sellado

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~495 (models 55 + migration 45 + admin 45 + views 12 + seed 110 + tests 230) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | 3 chained PRs (feature-branch-chain) |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending (recommend feature-branch-chain) |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Models + migration + model-method tests | PR 1 | base = feature/tracker `feat/menu-combo-sellado`; autonomous slice 1 |
| 2 | `poblar_datos` rewrite + `--reset` + integration tests | PR 2 | base = PR 1 branch |
| 3 | `pos_view` wiring + admin registration + view/admin tests | PR 3 | base = PR 2 branch |

### Decision to resolve before apply
- **Taper gate = order-level `tipo_servicio=LLEVAR` only** (per-detail `es_para_llevar` NOT part of taper count). Keeps model methods in sync with spec/scenarios. Per-detail flag stays stored only for POS/kitchen display.

## Phase 1: Models & Migration

- [x] 1.1 RED `restaurante/tests.py`: `MenuModelTest` (fixed price persist, admin-editable, `activo=False` excluded) per menu-combo scenarios.
- [x] 1.2 GREEN `restaurante/models.py`: add `Menu` (2 PROTECT FKs `categoria_entrada`/`categoria_segundo`, `precio` default 13.00, `nombre` default "Menú", `activo`).
- [x] 1.3 RED tests: `Configuracion.get()` default `recargo_por_taper=1.00` + id=1 singleton.
- [x] 1.4 GREEN: add `Configuracion` model + `Configuracion.get()`.
- [x] 1.5 RED tests: `DetalleOrden.taper_count()` (sopa=1, segundo=1, menu=2, añadido=0) + `subtotal()` unchanged.
- [x] 1.6 GREEN: `DetalleOrden.menu` FK (null=True), nullable `plato`, `taper_count()`.
- [x] 1.7 RED tests: `Orden.computar_total()` LLEVAR vs MESA (scenarios 15.00 / no surcharge / añadidos).
- [x] 1.8 GREEN: `Orden.computar_total()` = `sum(subtotal()) + tapers×recargo` only if `LLEVAR`.
- [x] 1.9 `makemigrations restaurante` → create `0008_*.py` (Menu, Configuracion, DetalleOrden.menu, plato nullable); run `migrate`.

## Phase 2: Seed & Reset

- [x] 2.1 RED tests: seed yields exact catalog (1 Entrada 6.00, 10 Segundos 11.00, 3 Añadidos) + determinism (run twice).
- [x] 2.2 RED tests: `--reset` clears-then-reseeds + idempotent (twice, no duplicate rows, no `ProtectedError`).
- [x] 2.3 GREEN rewrite `poblar_datos.py`: deterministic seed (Categoria, Plato, Menu, Configuracion), `--reset` soft-deactivates+upserts (never `.delete()`), keep superuser creation.

## Phase 3: Wire & Admin

- [ ] 3.1 RED test: `pos_view` POST with menu line + LLEVAR persists `orden.total` with surcharge; MESA without (view scenarios).
- [ ] 3.2 GREEN `restaurante/views.py`: `pos_view` builds details (plato OR menu) then `orden.total = orden.computar_total()`.
- [ ] 3.3 RED admin smoke: Menu + Configuracion registered/editable (full admin editability scenario).
- [ ] 3.4 GREEN `restaurante/admin.py`: register `Menu`; `Configuracion` admin (`has_add_permission=False`); update `DetalleOrdenInline` for `menu`.

## Phase 4: Verify

- [ ] 4.1 Run full suite: `DATABASE_URL=sqlite:///./db.sqlite3 python manage.py test` (all pass).
- [ ] 4.2 `python manage.py check` + `ruff check .` clean.

Chain boundary (slice 1): Tasks 1.1–1.9 → PR 1. Slice 2: 2.1–2.3 → PR 2. Slice 3: 3.1–4.2 → PR 3.