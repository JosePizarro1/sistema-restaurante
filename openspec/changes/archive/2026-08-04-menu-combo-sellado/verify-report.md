# Verification Report — menu-combo-sellado

**Change**: menu-combo-sellado
**Version**: delta spec (ADDED only; openspec/specs empty)
**Mode**: Strict TDD (config.yaml `strict_tdd: true`, runner django)
**Branch**: `feat/menu-combo-sellado-wire`
**Command**: `DATABASE_URL=sqlite:///./db.sqlite3 ./venv/bin/python manage.py test restaurante`

## Completeness

| Metric | Value |
|--------|-------|
| Tasks total | 12 |
| Tasks complete | 12 |
| Tasks incomplete | 0 |

All 12 tasks marked `[x]` in `tasks.md` and confirmed complete across apply-progress (slices 1–3 + PR2 + PR3 fixes).

## Build & Tests Execution

**Build (`manage.py check`)**: ✅ Passed — `System check identified no issues (0 silenced).`

**Tests**: ✅ 64 passed / 0 failed / 0 skipped
```text
Ran 64 tests in 10.831s
OK
```
(migrations 0008–0010 already applied on dev SQLite; `migrate` reported "No migrations to apply.")

**Coverage**: ➖ Not available — `coverage` module not installed; config.yaml `coverage: false`.

**Linter (ruff)**: ⚠️ 20 errors — ALL are `RUF012` (mutable default) on Django-generated migration files, including pre-existing 0001–0007. No errors in `models.py`, `views.py`, `admin.py`, `poblar_datos.py`, or `tests.py`. No ruff config file exists to exclude migrations. Task 4.2's "`ruff check .` clean" claim is inaccurate.

## Spec Compliance Matrix (19 scenarios)

| Req | Scenario | Test | Result |
|-----|----------|------|--------|
| Menu sealed-combo entity | Create sealed combo fixed price | `tests.py > MenuModelTest.test_menu_defaults` + `test_menu_references_entrada_and_segundo_categories` | ✅ COMPLIANT |
| Menu sealed-combo entity | Any entrada + any segundo accepted | `tests.py > MenuModelTest.test_menu_line_prices_as_a_unit` (Sopa de Res + Lomo Saltado) | ✅ COMPLIANT (category-driven by design D1) |
| Menu sealed-combo entity | Menu price admin-editable | `tests.py > MenuModelTest.test_menu_price_admin_editable` | ✅ COMPLIANT |
| Menu sealed-combo entity | Inactive menu unavailable | `tests.py > MenuModelTest.test_inactive_menu_is_unavailable` + `Pr3MenuComboFixesTest.test_post_inactive_menu_returns_404` | ✅ COMPLIANT |
| Menu pricing as a unit | Line prices at fixed menu price | `tests.py > MenuModelTest.test_menu_line_prices_as_a_unit` (2×13.00=26.00, not 6+11) | ✅ COMPLIANT |
| Menu pricing as a unit | Menu + añadidos sum without taper penalty | `tests.py > OrdenComputarTotalTest.test_menu_plus_anadidos_sum_without_taper_penalty` (16.50) | ✅ COMPLIANT |
| Configurable per-taper surcharge | Default surcharge seeded | `tests.py > ConfiguracionModelTest.test_get_returns_singleton_with_default_recargo` (1.00) + `test_get_never_duplicates_singleton` | ✅ COMPLIANT |
| Configurable per-taper surcharge | Surcharge admin-editable | `tests.py > ConfiguracionModelTest.test_recargo_admin_editable` + `OrdenComputarTotalTest.test_editable_recargo_changes_llevar_total` | ✅ COMPLIANT |
| Taper counting (LLEVAR) | Solo sopa = 1 taper | `tests.py > DetalleOrdenTaperTest.test_sopa_counts_one_taper` | ✅ COMPLIANT |
| Taper counting (LLEVAR) | Solo segundo = 1 taper | `tests.py > DetalleOrdenTaperTest.test_segundo_counts_one_taper` | ✅ COMPLIANT |
| Taper counting (LLEVAR) | Sopa + segundo = 2 tapers | `tests.py > OrdenComputarTotalTest.test_llevar_sopa_plus_segundo_two_tapers` (19.00) + `DetalleOrdenTaperTest.test_menu_counts_two_tapers` | ✅ COMPLIANT |
| Taper counting (LLEVAR) | Añadidos do not add tapers | `tests.py > DetalleOrdenTaperTest.test_anadido_counts_zero_tapers` + `test_llevar_anadidos_add_no_surcharge` | ✅ COMPLIANT |
| Surcharge only LLEVAR | LLEVAR total includes surcharge | `tests.py > OrdenComputarTotalTest.test_llevar_menu_total_includes_surcharge` (15.00) + `PosViewTotalTest.test_llevar_menu_line_total_includes_surcharge` | ✅ COMPLIANT |
| Surcharge only LLEVAR | MESA total has no surcharge | `tests.py > OrdenComputarTotalTest.test_mesa_menu_total_has_no_surcharge` (13.00) + `PosViewTotalTest.test_mesa_menu_line_total_has_no_surcharge` | ✅ COMPLIANT |
| Real seeded catalog | Seed creates exact catalog | `tests.py > PoblarDatosSeedTest.test_seed_creates_exact_catalog` (1 Entrada 6.00, 10 Segundos 11.00, 3 Añadidos) + `test_seed_creates_menu_with_price_and_category_refs` | ✅ COMPLIANT |
| Real seeded catalog | Seed is deterministic | `tests.py > PoblarDatosSeedTest.test_seed_is_deterministic_and_idempotent` | ✅ COMPLIANT |
| Seed reset mode | Reset clears then reseeds | `tests.py > PoblarDatosResetTest.test_reset_clears_then_reseeds_and_deactivates_stale` + `test_reset_restores_canonical_pricing` | ✅ COMPLIANT |
| Seed reset mode | Reset is idempotent | `tests.py > PoblarDatosResetTest.test_reset_is_idempotent_no_duplicates` | ✅ COMPLIANT |
| Full admin editability | Admin can manage all catalog entities | `tests.py > AdminRegistrationTest.test_menu_and_configuracion_registered_in_site` + `test_menu_add_page_renders_editable_fields` + `test_configuracion_not_addable_but_editable` | ✅ COMPLIANT |

**Compliance summary**: 19/19 scenarios compliant (15 named in the launch prompt; the file actually contains 19 scenario blocks — 4 additional under sealed-combo entity + taper counting that were not enumerated in the prompt, all covered).

No requirement, scenario, or task without evidence.

## Correctness (Static Evidence)

| Capability | Status | Notes |
|------------|--------|-------|
| menu-combo | ✅ Implemented | `Menu` model (2 PROTECT FKs to Categoria, fixed editable `precio` default 13.00, `nombre` "Menú", `activo`); `DetalleOrden.menu` FK + XOR CheckConstraint (migration 0010); Menu line bills as unit. |
| takeout-pricing | ✅ Implemented | `Configuracion` singleton (`get()`, id=1) + `recargo_por_taper` default 1.00; `DetalleOrden.taper_count()` (menu=2×cantidad, packable plato=cantidad, else 0); `Orden.computar_total()` adds surcharge only when `tipo_servicio='LLEVAR'`. Packability is intrinsic to `Categoria.packable` (default False), not Menu presence (design D2). |
| catalog-management | ✅ Implemented | Deterministic `poblar_datos` seed (exact catalog, Menu 13.00, surcharge 1.00); `--reset` soft-deactivates (never `.delete()`, PROTECT-safe) then upserts; admin edits preserved on plain run, canonical prices forced on `--reset`; Menu + Configuracion registered in admin; `Categoria`/`Plato` admin already editable. |

## Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| D1 — 2 FKs to Categoria (PROTECT) | ✅ Yes | `categoria_entrada`/`categoria_segundo` with `on_delete=PROTECT`. |
| D2 — taper from Categoria.packable | ✅ Yes | `packable` default False; regression tests `NoMenuALaCarteTaperTest`, `CategoriaPackableDefaultTest`. |
| D3 — Configuracion singleton (id=1) | ✅ Yes | `get()`, admin `has_add_permission=False`, `has_delete_permission=False`. |
| D4 — surcharge in model methods | ✅ Yes | `Orden.computar_total()`; `pos_view` sets `orden.total = orden.computar_total()`. |
| D5 — reset soft-deactivate + upsert | ✅ Yes | `_reconcile_*` update `activo=False` then get_or_create; never `.delete()`. |

## TDD Compliance

| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | ✅ | apply-progress `sdd/menu-combo-sellado/apply-progress` present with TDD Cycle Evidence table. |
| All tasks have tests | ✅ | 12/12 tasks backed by covering tests in `restaurante/tests.py`. |
| RED confirmed (tests exist) | ✅ | Test files verified on disk. |
| GREEN confirmed (tests pass) | ✅ | 64/64 pass on execution (64 > baseline 57; PR3 batch added 7). |
| Triangulation adequate | ✅ | Multiple distinct-value assertions per behavior (e.g. taper counts 1/2/0/6; totals 15.00/13.00/16.50/19.00). |
| Safety Net for modified files | ✅ | apply-progress reports 57/57 baseline before each slice's changes. |

**TDD Compliance**: 6/6 checks passed.

## Test Layer Distribution

| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | ~28 | 1 (`restaurante/tests.py`) | Django TestCase |
| Integration | ~24 | 1 | Django `Client` (view/POST) |
| Admin smoke | ~7 | 1 | Django test `Client` + `admin.site` |
| **Total** | **64** | **1** | |

## Assertion Quality

**Assertion quality**: ✅ All assertions verify real behavior — assert concrete Decimal totals, counts, HTTP status codes, and entity references. No tautologies, no ghost loops, no smoke-only, no type-only assertions. Triangulation good (varying expected values).

## Issues Found

**CRITICAL**: None.

**WARNING**:
- W1 — Task 4.2 (tasks.md) claims "`ruff check .` clean", but `ruff check .` reports 20 `RUF012` errors. All are on Django-generated migration files (0001–0010, including pre-existing 0001–0007), and none on changed source files. Mitigating: no ruff config exists; this is a repo-wide false-positive pattern. Maps to task 4.2 (verify gate) — does not violate a spec scenario.

**SUGGESTION**:
- S1 — Design.md "Open Questions" still lists `[ ]` for the per-detail `es_para_llevar` taper gate and sync question; `tasks.md` resolved it (taper = order-level `tipo_servicio=LLEVAR` only). Update design.md to reflect the resolution.
- S2 — `templates/pos.html` has no Menu-selection card UI (residual frontend task flagged in apply-progress, out of backend slice scope). Menu lines are orderable via the API but not yet via the POS UI.
- S3 — Add a ruff config to exclude `migrations/` (or ignore `RUF012`) to silence the 20 false positives and make `ruff check .` genuinely clean.

## Verdict

**PASS WITH WARNINGS** — Full suite green (64/64), all 12 tasks complete, all 19 spec scenarios covered by passing tests, design D1–D5 followed. Single WARNING is a non-blocking ruff claim inaccuracy on pre-existing migration files.

## Next Recommended

- Archive (`sdd-archive`) to sync the delta spec into `openspec/specs/`.
- Before PR merge: resolve S2 (POS Menu card UI) if in scope for the next change; optionally apply S3 ruff config.
