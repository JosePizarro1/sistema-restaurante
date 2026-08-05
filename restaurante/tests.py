import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib import admin as dj_admin
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse

from .models import Ambiente, Categoria, Configuracion, DetalleOrden, Menu, Mesa, Orden, Plato


class CategoriaModelTest(TestCase):
    def setUp(self):
        self.cat1 = Categoria.objects.create(nombre='Entradas', orden=1)
        self.cat2 = Categoria.objects.create(nombre='Bebidas', orden=2)

    def test_categoria_creation(self):
        self.assertEqual(self.cat1.nombre, 'Entradas')
        self.assertEqual(str(self.cat1), 'Entradas')
        self.assertTrue(self.cat1.activo)

    def test_categoria_ordering(self):
        categorias = list(Categoria.objects.all())
        self.assertEqual(categorias, [self.cat1, self.cat2])


class PlatoModelTest(TestCase):
    def setUp(self):
        self.cat = Categoria.objects.create(nombre='Picantería Arequipeña', orden=1)
        self.plato = Plato.objects.create(nombre='Rocoto Relleno', precio=25.50, categoria=self.cat)

    def test_plato_creation(self):
        self.assertEqual(self.plato.nombre, 'Rocoto Relleno')
        self.assertEqual(self.plato.categoria, self.cat)
        self.assertEqual(str(self.plato), 'Rocoto Relleno - S/. 25.5')


class OrdenModelTest(TestCase):
    def setUp(self):
        self.plato = Plato.objects.create(nombre='Chupe de Camarones', precio=35.00)
        self.orden = Orden.objects.create(metodo_pago='PENDIENTE', estado='PENDIENTE', total=70.00)
        self.detalle = DetalleOrden.objects.create(orden=self.orden, plato=self.plato, cantidad=2, precio_unitario=35.00)

    def test_subtotal_calculation(self):
        self.assertEqual(self.detalle.subtotal(), 70.00)
        self.assertEqual(self.orden.detalles.count(), 1)


class ViewsAccessTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='mozo', password='password123')
        self.admin = User.objects.create_superuser(username='admin', password='password123')

    def test_pos_view_redirects_unauthenticated(self):
        response = self.client.get(reverse('pos'))
        self.assertEqual(response.status_code, 302)

    def test_pos_view_authenticated(self):
        self.client.login(username='mozo', password='password123')
        response = self.client.get(reverse('pos'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('categorias', response.context)

    def test_api_cocina_ordenes(self):
        self.client.login(username='mozo', password='password123')
        response = self.client.get(reverse('api_cocina_ordenes'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('ordenes', response.json())


class ModoImpresionTest(TestCase):
    """Modo impresión: la pantalla de cocina no lista órdenes y el POS
    oculta el tab 'Por Cobrar' (las comandas se entregan en papel)."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='mozo', password='password123')
        self.orden = Orden.objects.create(
            metodo_pago='PENDIENTE', estado='PENDIENTE', tipo_servicio='MESA', total=25.00
        )

    def tearDown(self):
        # Restaurar el modo por defecto para no contaminar otros tests.
        cfg = Configuracion.get()
        cfg.modo_envio = 'KITCHEN'
        cfg.save()

    def test_cocina_lists_orders_in_kitchen_mode(self):
        self.client.login(username='mozo', password='password123')
        response = self.client.get(reverse('cocina'))
        self.assertContains(response, f'data-orden-id="{self.orden.id}"')

    def test_cocina_does_not_list_orders_in_print_mode(self):
        cfg = Configuracion.get()
        cfg.modo_envio = 'PRINT'
        cfg.save()
        self.client.login(username='mozo', password='password123')
        response = self.client.get(reverse('cocina'))
        self.assertNotContains(response, f'data-orden-id="{self.orden.id}"')
        self.assertContains(response, 'Modo impresión activo')

    def test_api_cocina_ordenes_empty_in_print_mode(self):
        cfg = Configuracion.get()
        cfg.modo_envio = 'PRINT'
        cfg.save()
        self.client.login(username='mozo', password='password123')
        response = self.client.get(reverse('api_cocina_ordenes'))
        self.assertEqual(response.json(), {'ordenes': []})

    def test_pos_hides_cobrar_tab_in_print_mode(self):
        cfg = Configuracion.get()
        cfg.modo_envio = 'PRINT'
        cfg.save()
        self.client.login(username='mozo', password='password123')
        response = self.client.get(reverse('pos'))
        self.assertNotContains(response, 'id="tab-btn-cobrar"')

    def test_pos_shows_cobrar_tab_in_kitchen_mode(self):
        self.client.login(username='mozo', password='password123')
        response = self.client.get(reverse('pos'))
        self.assertContains(response, 'id="tab-btn-cobrar"')


class CategoriaCRUDTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(username='admin', password='password123')
        self.client.login(username='admin', password='password123')

    def test_categorias_list_view(self):
        Categoria.objects.create(nombre='Postres', orden=1)
        response = self.client.get(reverse('categorias_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Postres')

    def test_categoria_create_view(self):
        response = self.client.post(reverse('categoria_create'), {'nombre': 'Jugos Naturales', 'orden': 3, 'activo': 'on'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Categoria.objects.filter(nombre='Jugos Naturales').exists())

    def test_categoria_edit_view(self):
        cat = Categoria.objects.create(nombre='Antigua', orden=1)
        response = self.client.post(reverse('categoria_edit', args=[cat.id]), {'nombre': 'Editada', 'orden': 5, 'activo': 'on'})
        self.assertEqual(response.status_code, 302)
        cat.refresh_from_db()
        self.assertEqual(cat.nombre, 'Editada')

    def test_categoria_delete_view(self):
        cat = Categoria.objects.create(nombre='Para Borrar', orden=1)
        response = self.client.post(reverse('categoria_delete', args=[cat.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Categoria.objects.filter(id=cat.id).exists())


class MenuModelTest(TestCase):
    def setUp(self):
        self.entrada = Categoria.objects.create(nombre='Entrada', orden=1)
        self.segundo = Categoria.objects.create(nombre='Segundo', orden=2)
        self.menu = Menu.objects.create(
            categoria_entrada=self.entrada,
            categoria_segundo=self.segundo,
        )

    def test_menu_defaults(self):
        self.assertEqual(self.menu.nombre, 'Menú')
        self.assertEqual(self.menu.precio, Decimal('13.00'))
        self.assertTrue(self.menu.activo)

    def test_menu_price_admin_editable(self):
        self.menu.precio = Decimal('15.00')
        self.menu.save()
        self.menu.refresh_from_db()
        self.assertEqual(self.menu.precio, Decimal('15.00'))

    def test_menu_references_entrada_and_segundo_categories(self):
        self.assertEqual(self.menu.categoria_entrada, self.entrada)
        self.assertEqual(self.menu.categoria_segundo, self.segundo)

    def test_inactive_menu_is_unavailable(self):
        # Scenario: "Inactive menu is unavailable" — activo=False must be excluded
        # from selectable options while the active one remains.
        inactivo = Menu.objects.create(
            categoria_entrada=self.entrada,
            categoria_segundo=self.segundo,
            activo=False,
        )
        disponibles = list(Menu.objects.filter(activo=True))
        self.assertNotIn(inactivo, disponibles)
        self.assertIn(self.menu, disponibles)

    def test_menu_line_prices_as_a_unit(self):
        # Any Entrada + any Segundo from the eligible categories: fixed menu price,
        # not the sum of the constituent platos.
        Plato.objects.create(nombre='Sopa de Res', precio=6.00, categoria=self.entrada)
        Plato.objects.create(nombre='Lomo Saltado', precio=11.00, categoria=self.segundo)
        orden = Orden.objects.create(tipo_servicio='MESA')
        detalle = DetalleOrden.objects.create(
            orden=orden,
            menu=self.menu,
            cantidad=2,
            precio_unitario=self.menu.precio,
        )
        self.assertEqual(detalle.subtotal(), Decimal('26.00'))


class ConfiguracionModelTest(TestCase):
    def test_get_returns_singleton_with_default_recargo(self):
        cfg = Configuracion.get()
        self.assertEqual(cfg.id, 1)
        self.assertEqual(cfg.recargo_por_taper, Decimal('1.00'))

    def test_recargo_admin_editable(self):
        cfg = Configuracion.get()
        cfg.recargo_por_taper = Decimal('2.00')
        cfg.save()
        self.assertEqual(Configuracion.get().recargo_por_taper, Decimal('2.00'))

    def test_get_never_duplicates_singleton(self):
        Configuracion.get()
        Configuracion.get()
        self.assertEqual(Configuracion.objects.count(), 1)

    def test_modo_envio_defaults_to_kitchen(self):
        # APP-CONF-1: default KITCHEN keeps backward-compatible behavior.
        cfg = Configuracion.get()
        self.assertEqual(cfg.modo_envio, 'KITCHEN')

    def test_modo_envio_persists_print(self):
        cfg = Configuracion.get()
        cfg.modo_envio = 'PRINT'
        cfg.save()
        cfg.refresh_from_db()
        self.assertEqual(cfg.modo_envio, 'PRINT')


class ConfiguracionViewTest(TestCase):
    """APP-CONF-2: superuser-only settings page toggling modo_envio with
    validation and success/error messages."""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(username='admin', password='password123')
        self.mozo = User.objects.create_user(username='mozo', password='password123')
        self.url = reverse('configuracion')

    def test_get_renders_form_with_choices_for_superuser(self):
        self.client.login(username='admin', password='password123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="modo_envio"')
        self.assertContains(response, 'value="KITCHEN"')
        self.assertContains(response, 'value="PRINT"')

    def test_post_valid_print_persists_and_redirects(self):
        self.client.login(username='admin', password='password123')
        response = self.client.post(self.url, {'modo_envio': 'PRINT'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Configuracion.get().modo_envio, 'PRINT')

    def test_post_valid_kitchen_persists(self):
        cfg = Configuracion.get()
        cfg.modo_envio = 'PRINT'
        cfg.save()
        self.client.login(username='admin', password='password123')
        response = self.client.post(self.url, {'modo_envio': 'KITCHEN'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Configuracion.get().modo_envio, 'KITCHEN')

    def test_non_superuser_post_denied_no_mutation(self):
        self.client.login(username='mozo', password='password123')
        response = self.client.post(self.url, {'modo_envio': 'PRINT'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Configuracion.get().modo_envio, 'KITCHEN')

    def test_unauthenticated_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_invalid_value_rejected_field_unchanged(self):
        self.client.login(username='admin', password='password123')
        response = self.client.post(self.url, {'modo_envio': 'FAX'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Configuracion.get().modo_envio, 'KITCHEN')


class DetalleOrdenTaperTest(TestCase):
    def setUp(self):
        self.entrada = Categoria.objects.create(nombre='Entrada', orden=1, packable=True)
        self.segundo = Categoria.objects.create(nombre='Segundo', orden=2, packable=True)
        self.anadidos = Categoria.objects.create(nombre='Añadidos', orden=3, packable=False)
        self.menu = Menu.objects.create(
            categoria_entrada=self.entrada,
            categoria_segundo=self.segundo,
        )
        self.sopa = Plato.objects.create(nombre='Sopa de Res', precio=6.00, categoria=self.entrada)
        self.segundo_plato = Plato.objects.create(nombre='Lomo Saltado', precio=11.00, categoria=self.segundo)
        self.huevo = Plato.objects.create(nombre='Huevo', precio=1.50, categoria=self.anadidos)
        self.orden = Orden.objects.create(tipo_servicio='LLEVAR')

    def _detail(self, plato=None, menu=None, cantidad=1):
        precio = plato.precio if plato else menu.precio
        return DetalleOrden.objects.create(
            orden=self.orden,
            plato=plato,
            menu=menu,
            cantidad=cantidad,
            precio_unitario=precio,
        )

    def test_sopa_counts_one_taper(self):
        self.assertEqual(self._detail(plato=self.sopa).taper_count(), 1)

    def test_segundo_counts_one_taper(self):
        self.assertEqual(self._detail(plato=self.segundo_plato).taper_count(), 1)

    def test_menu_counts_two_tapers(self):
        self.assertEqual(self._detail(menu=self.menu).taper_count(), 2)

    def test_anadido_counts_zero_tapers(self):
        self.assertEqual(self._detail(plato=self.huevo).taper_count(), 0)

    def test_menu_cantidad_scales_tapers(self):
        self.assertEqual(self._detail(menu=self.menu, cantidad=3).taper_count(), 6)


class OrdenComputarTotalTest(TestCase):
    def setUp(self):
        self.entrada = Categoria.objects.create(nombre='Entrada', orden=1, packable=True)
        self.segundo = Categoria.objects.create(nombre='Segundo', orden=2, packable=True)
        self.anadidos = Categoria.objects.create(nombre='Añadidos', orden=3, packable=False)
        self.menu = Menu.objects.create(
            categoria_entrada=self.entrada,
            categoria_segundo=self.segundo,
        )
        self.sopa = Plato.objects.create(nombre='Sopa de Res', precio=6.00, categoria=self.entrada)
        self.segundo_plato = Plato.objects.create(nombre='Lomo Saltado', precio=11.00, categoria=self.segundo)
        self.huevo = Plato.objects.create(nombre='Huevo', precio=1.50, categoria=self.anadidos)

    def test_llevar_menu_total_includes_surcharge(self):
        orden = Orden.objects.create(tipo_servicio='LLEVAR')
        DetalleOrden.objects.create(orden=orden, menu=self.menu, cantidad=1, precio_unitario=Decimal('13.00'))
        self.assertEqual(orden.computar_total(), Decimal('15.00'))

    def test_mesa_menu_total_has_no_surcharge(self):
        orden = Orden.objects.create(tipo_servicio='MESA')
        DetalleOrden.objects.create(orden=orden, menu=self.menu, cantidad=1, precio_unitario=Decimal('13.00'))
        self.assertEqual(orden.computar_total(), Decimal('13.00'))

    def test_menu_plus_anadidos_sum_without_taper_penalty(self):
        # Scenario: "Menu + añadidos sum without taper penalty" — a LLEVAR order
        # with one Menu + one Huevo surcharges only the two menu tapers
        # (sopa + segundo); the añadido adds only its price and 0 tapers.
        orden = Orden.objects.create(tipo_servicio='LLEVAR')
        DetalleOrden.objects.create(orden=orden, menu=self.menu, cantidad=1, precio_unitario=Decimal('13.00'))
        huevo_linea = DetalleOrden.objects.create(orden=orden, plato=self.huevo, cantidad=1, precio_unitario=Decimal('1.50'))
        # huevo (Añadidos) never packs
        self.assertEqual(huevo_linea.taper_count(), 0)
        # 13.00 + 1.50 + (2 × 1.00) = 16.50
        self.assertEqual(orden.computar_total(), Decimal('16.50'))

    def test_llevar_sopa_plus_segundo_two_tapers(self):
        orden = Orden.objects.create(tipo_servicio='LLEVAR')
        DetalleOrden.objects.create(orden=orden, plato=self.sopa, cantidad=1, precio_unitario=Decimal('6.00'))
        DetalleOrden.objects.create(
            orden=orden,
            plato=self.segundo_plato,
            cantidad=1,
            precio_unitario=Decimal('11.00'),
        )
        # 6.00 + 11.00 + (2 tapers × 1.00) = 19.00
        self.assertEqual(orden.computar_total(), Decimal('19.00'))

    def test_llevar_anadidos_add_no_surcharge(self):
        orden = Orden.objects.create(tipo_servicio='LLEVAR')
        DetalleOrden.objects.create(orden=orden, plato=self.huevo, cantidad=1, precio_unitario=Decimal('1.50'))
        self.assertEqual(orden.computar_total(), Decimal('1.50'))

    def test_editable_recargo_changes_llevar_total(self):
        cfg = Configuracion.get()
        cfg.recargo_por_taper = Decimal('2.00')
        cfg.save()
        orden = Orden.objects.create(tipo_servicio='LLEVAR')
        DetalleOrden.objects.create(orden=orden, menu=self.menu, cantidad=1, precio_unitario=Decimal('13.00'))
        # 13.00 + (2 tapers × 2.00) = 17.00
        self.assertEqual(orden.computar_total(), Decimal('17.00'))


class NoMenuALaCarteTaperTest(TestCase):
    """Regression for the critical fix: packability MUST NOT depend on an
    active Menu row existing. Packability is modeled on the Categoria itself."""

    def setUp(self):
        # No Menu is created in this test at all.
        self.entrada = Categoria.objects.create(nombre='Entrada', orden=1, packable=True)
        self.segundo = Categoria.objects.create(nombre='Segundo', orden=2, packable=True)
        self.anadidos = Categoria.objects.create(nombre='Añadidos', orden=3, packable=False)
        self.sopa = Plato.objects.create(nombre='Sopa de Res', precio=6.00, categoria=self.entrada)
        self.segundo_plato = Plato.objects.create(nombre='Lomo Saltado', precio=11.00, categoria=self.segundo)
        self.huevo = Plato.objects.create(nombre='Huevo', precio=1.50, categoria=self.anadidos)

    def test_sopa_segundo_a_la_carte_still_surcharge_when_no_menu_exists(self):
        self.assertFalse(Menu.objects.exists())
        orden = Orden.objects.create(tipo_servicio='LLEVAR')
        DetalleOrden.objects.create(orden=orden, plato=self.sopa, cantidad=1, precio_unitario=Decimal('6.00'))
        DetalleOrden.objects.create(
            orden=orden,
            plato=self.segundo_plato,
            cantidad=1,
            precio_unitario=Decimal('11.00'),
        )
        # 6.00 + 11.00 + (2 × 1.00) = 19.00 — surcharge survives with no Menu
        self.assertEqual(orden.computar_total(), Decimal('19.00'))

    def test_anadido_still_zero_tapers_with_no_menu(self):
        self.assertFalse(Menu.objects.exists())
        orden = Orden.objects.create(tipo_servicio='LLEVAR')
        linea = DetalleOrden.objects.create(orden=orden, plato=self.huevo, cantidad=1, precio_unitario=Decimal('1.50'))
        self.assertEqual(linea.taper_count(), 0)


class DetalleOrdenValidationTest(TestCase):
    """Issue 2: a DetalleOrden must reference exactly one of plato/menu."""

    def setUp(self):
        self.cat = Categoria.objects.create(nombre='Añadidos', orden=1, packable=False)
        self.plato = Plato.objects.create(nombre='Huevo', precio=1.50, categoria=self.cat)
        self.orden = Orden.objects.create(tipo_servicio='MESA')

    def _linea(self, plato=None, menu=None):
        return DetalleOrden(
            orden=self.orden,
            plato=plato,
            menu=menu,
            cantidad=1,
            precio_unitario=Decimal('1.50'),
        )

    def test_rejects_line_with_neither_plato_nor_menu(self):
        with self.assertRaises(ValidationError):
            self._linea().full_clean()

    def test_rejects_line_with_both_plato_and_menu(self):
        entrada = Categoria.objects.create(nombre='Entrada', orden=2)  # packable default False (irrelevant to XOR validation)
        menu = Menu.objects.create(categoria_entrada=entrada, categoria_segundo=self.cat)
        with self.assertRaises(ValidationError):
            self._linea(plato=self.plato, menu=menu).full_clean()

    def test_accepts_line_with_exactly_one(self):
        # exactly one (plato) is valid — full_clean must not raise
        self._linea(plato=self.plato).full_clean()

    def test_db_constraint_rejects_line_with_neither_plato_nor_menu(self):
        # objects.create bypasses clean(); the DB CheckConstraint must reject
        # a persisted line with neither plato nor menu.
        with self.assertRaises(IntegrityError):
            DetalleOrden.objects.create(
                orden=self.orden,
                plato=None,
                menu=None,
                cantidad=1,
                precio_unitario=Decimal('1.50'),
            )

    def test_db_constraint_rejects_line_with_both_plato_and_menu(self):
        entrada = Categoria.objects.create(nombre='Entrada', orden=2, packable=True)
        menu = Menu.objects.create(categoria_entrada=entrada, categoria_segundo=self.cat)
        with self.assertRaises(IntegrityError):
            DetalleOrden.objects.create(
                orden=self.orden,
                plato=self.plato,
                menu=menu,
                cantidad=1,
                precio_unitario=Decimal('1.50'),
            )


class CategoriaPackableDefaultTest(TestCase):
    """Issue 1 regression: Categoria.packable MUST default to False so a newly
    added category (admin-editable, no code change) does NOT silently incur a
    "para llevar" taper surcharge. Packability is opt-in per category."""

    def test_packable_defaults_to_false(self):
        cat = Categoria.objects.create(nombre='Nueva Categoría', orden=1)
        self.assertFalse(cat.packable)

    def test_non_packable_category_does_not_surcharge_on_llevar(self):
        # Category created WITHOUT packable=True (default False) must not taper.
        no_pack = Categoria.objects.create(nombre='Extras', orden=1)
        plato = Plato.objects.create(nombre='Extra', precio=4.00, categoria=no_pack)
        orden = Orden.objects.create(tipo_servicio='LLEVAR')
        DetalleOrden.objects.create(orden=orden, plato=plato, cantidad=1, precio_unitario=Decimal('4.00'))
        # 0 tapers -> total is just the price, no surcharge
        self.assertEqual(orden.computar_total(), Decimal('4.00'))

    def test_packable_category_surcharges_on_llevar(self):
        # Category created WITH packable=True must taper on LLEVAR.
        pack = Categoria.objects.create(nombre='Segundo', orden=2, packable=True)
        plato = Plato.objects.create(nombre='Lomo Saltado', precio=11.00, categoria=pack)
        orden = Orden.objects.create(tipo_servicio='LLEVAR')
        DetalleOrden.objects.create(orden=orden, plato=plato, cantidad=1, precio_unitario=Decimal('11.00'))
        # 11.00 + (1 taper × 1.00) = 12.00
        self.assertEqual(orden.computar_total(), Decimal('12.00'))


class PoblarDatosSeedTest(TestCase):
    """Task 2.1 — seed yields the exact real catalog and is deterministic.

    Integration tests against the `poblar_datos` management command (catalog
    scenarios: "Seed creates the exact catalog", "Seed is deterministic")."""

    def _run(self, reset=False):
        call_command('poblar_datos', reset=reset)

    def _catalog_state(self):
        """Normalized, sortable snapshot of the seeded catalog."""
        return {
            'categorias': sorted(Categoria.objects.values_list('nombre', 'packable', 'activo', 'orden')),
            'platos': sorted(Plato.objects.values_list('categoria__nombre', 'nombre', 'precio', 'activo')),
            'menus': sorted(Menu.objects.values_list('nombre', 'precio', 'categoria_entrada__nombre', 'categoria_segundo__nombre', 'activo')),
            'config': Decimal(Configuracion.get().recargo_por_taper),
        }

    def test_seed_creates_exact_catalog(self):
        self._run()
        # 3 categorías
        self.assertEqual(Categoria.objects.count(), 3)
        # 1 Entrada + 10 Segundos + 3 Añadidos = 14 platos
        self.assertEqual(Plato.objects.count(), 14)

        entrada = Categoria.objects.get(nombre='Entrada')
        segundo = Categoria.objects.get(nombre='Segundo')
        anadidos = Categoria.objects.get(nombre='Añadidos')

        # Entrada: Sopa de Res 6.00, packable=True
        sopa = Plato.objects.get(nombre='Sopa de Res', categoria=entrada)
        self.assertEqual(sopa.precio, Decimal('6.00'))
        self.assertTrue(entrada.packable)

        # Segundos: the 10 names, all 11.00, packable=True
        segundos = list(Plato.objects.filter(categoria=segundo))
        self.assertEqual(len(segundos), 10)
        self.assertTrue(all(p.precio == Decimal('11.00') for p in segundos))
        self.assertTrue(segundo.packable)
        self.assertEqual(
            {p.nombre for p in segundos},
            {
                'Lomo Saltado',
                'Pollo Dorado',
                'Hamburguesa al Plato',
                'Chuleta de Res',
                'Saltado de Mollejas',
                'Hígado Frito',
                'Pollo Broaster',
                'Riñón Saltado',
                'Chuleta de Chancho',
                'Arroz a la Cubana',
            },
        )

        # Añadidos: Huevo 1.50, Porción de Arroz 3.00, Porción de Papa 3.00, packable=False
        self.assertFalse(anadidos.packable)
        self.assertEqual(Plato.objects.get(nombre='Huevo', categoria=anadidos).precio, Decimal('1.50'))
        self.assertEqual(Plato.objects.get(nombre='Porción de Arroz', categoria=anadidos).precio, Decimal('3.00'))
        self.assertEqual(Plato.objects.get(nombre='Porción de Papa', categoria=anadidos).precio, Decimal('3.00'))

    def test_seed_creates_menu_with_price_and_category_refs(self):
        self._run()
        menu = Menu.objects.get(nombre='Menú')
        self.assertEqual(menu.precio, Decimal('13.00'))
        self.assertTrue(menu.activo)
        self.assertEqual(menu.categoria_entrada, Categoria.objects.get(nombre='Entrada'))
        self.assertEqual(menu.categoria_segundo, Categoria.objects.get(nombre='Segundo'))

    def test_seed_is_deterministic_and_idempotent(self):
        # Run twice from empty DB: identical state, no duplicate rows.
        self._run()
        first = self._catalog_state()
        platos_after_first = Plato.objects.count()
        categorias_after_first = Categoria.objects.count()
        self._run()
        self.assertEqual(Plato.objects.count(), platos_after_first)
        self.assertEqual(Categoria.objects.count(), categorias_after_first)
        self.assertEqual(self._catalog_state(), first)

    def test_seed_assigns_placeholder_image_to_every_new_plato(self):
        # Regression: the seed rewrite dropped demo-image generation, leaving
        # every seeded plato without an image (blank POS/menu cards). Every
        # newly seeded plato MUST end up with a non-empty imagen_base64.
        self._run()
        platos = list(Plato.objects.all())
        self.assertEqual(len(platos), 14)
        for plato in platos:
            self.assertTrue(plato.imagen_base64)
            self.assertTrue(plato.imagen_base64.startswith('data:image/'))

    def test_seed_does_not_overwrite_existing_plato_image(self):
        # Images are filled only when empty; an admin-assigned image must be kept.
        self._run()
        plato = Plato.objects.get(nombre='Lomo Saltado')
        plato.imagen_base64 = 'data:image/jpeg;base64,KEEP'
        plato.save()
        self._run()
        plato.refresh_from_db()
        self.assertEqual(plato.imagen_base64, 'data:image/jpeg;base64,KEEP')


class PoblarDatosResetTest(TestCase):
    """Task 2.2 — --reset clears-then-reseeds, soft-deactivates stale rows,
    never hits ProtectedError, and is idempotent."""

    def _run(self, reset=False):
        call_command('poblar_datos', reset=reset)

    def _catalog_state(self):
        return {
            'categorias': sorted(Categoria.objects.values_list('nombre', 'packable', 'activo', 'orden')),
            'platos': sorted(Plato.objects.values_list('categoria__nombre', 'nombre', 'precio', 'activo')),
            'menus': sorted(Menu.objects.values_list('nombre', 'precio', 'categoria_entrada__nombre', 'categoria_segundo__nombre', 'activo')),
            'config': Decimal(Configuracion.get().recargo_por_taper),
        }

    def test_reset_clears_then_reseeds_and_deactivates_stale(self):
        # Pre-existing stale catalog referencing a PROTECTed order row.
        stale_cat = Categoria.objects.create(nombre='Bebidas', orden=1, activo=True)
        stale_plato = Plato.objects.create(nombre='Inca Kola 1.5L', precio=9.00, categoria=stale_cat)
        orden = Orden.objects.create(tipo_servicio='MESA')
        # PROTECT on DetalleOrden.plato → seed must NOT hard-delete stale_plato.
        DetalleOrden.objects.create(orden=orden, plato=stale_plato, cantidad=1, precio_unitario=Decimal('9.00'))

        # Must not raise ProtectedError.
        self._run(reset=True)

        # Stale rows deactivated (not deleted), order intact.
        stale_cat.refresh_from_db()
        stale_plato.refresh_from_db()
        self.assertFalse(stale_cat.activo)
        self.assertFalse(stale_plato.activo)
        self.assertTrue(DetalleOrden.objects.filter(plato=stale_plato).exists())

        # Target catalog seeded; exactly the 3 seed categorías are active.
        self.assertEqual(Categoria.objects.filter(activo=True).count(), 3)
        self.assertFalse(Categoria.objects.get(nombre='Bebidas').activo)
        self.assertTrue(Categoria.objects.get(nombre='Entrada').activo)
        self.assertTrue(Plato.objects.get(nombre='Lomo Saltado').activo)

    def test_reset_reconciles_packable_flags(self):
        # Older rows may carry wrong packable (legacy default True); reset fixes them.
        Categoria.objects.create(nombre='Entrada', orden=1, packable=False, activo=True)
        Categoria.objects.create(nombre='Segundo', orden=2, packable=False, activo=True)
        Categoria.objects.create(nombre='Añadidos', orden=3, packable=True, activo=True)
        self._run(reset=True)
        self.assertTrue(Categoria.objects.get(nombre='Entrada').packable)
        self.assertTrue(Categoria.objects.get(nombre='Segundo').packable)
        self.assertFalse(Categoria.objects.get(nombre='Añadidos').packable)

    def test_reset_is_idempotent_no_duplicates(self):
        self._run(reset=True)
        cat_count = Categoria.objects.count()
        plato_count = Plato.objects.count()
        expected_state = self._catalog_state()
        self._run(reset=True)
        self.assertEqual(Categoria.objects.count(), cat_count)
        self.assertEqual(Plato.objects.count(), plato_count)
        self.assertEqual(self._catalog_state(), expected_state)

    def test_reset_reuses_legacy_row_with_matching_name_and_none_category(self):
        # Legacy row created by the OLD seed: same seed name but categoria=None.
        # It must be REUSED (re-parented to Segundo), NOT duplicated. D5 requires
        # re-parenting demo rows with real names instead of creating a second row.
        Categoria.objects.create(nombre='Entrada', orden=1, packable=True)
        Categoria.objects.create(nombre='Segundo', orden=2, packable=True)
        Categoria.objects.create(nombre='Añadidos', orden=3, packable=False)
        Plato.objects.create(nombre='Lomo Saltado', precio=8.00, categoria=None)

        self._run(reset=True)

        platos = Plato.objects.filter(nombre='Lomo Saltado')
        self.assertEqual(platos.count(), 1)
        plato = platos.first()
        self.assertEqual(plato.categoria, Categoria.objects.get(nombre='Segundo'))
        self.assertEqual(plato.precio, Decimal('11.00'))
        self.assertTrue(plato.activo)

    def test_plain_seed_does_not_clobber_admin_edited_pricing(self):
        # A NON-`--reset` run must reconcile structure but NOT overwrite
        # admin-edited Menu.precio, Configuracion.recargo_por_taper, or
        # existing Plato.precio (catalogo.md: all admin-editable).
        self._run()
        menu = Menu.objects.get(nombre='Menú')
        menu.precio = Decimal('15.00')
        menu.save()
        cfg = Configuracion.get()
        cfg.recargo_por_taper = Decimal('2.00')
        cfg.save()
        plato = Plato.objects.get(nombre='Lomo Saltado')
        plato.precio = Decimal('9.50')
        plato.save()

        self._run()

        self.assertEqual(Menu.objects.get(nombre='Menú').precio, Decimal('15.00'))
        self.assertEqual(Configuracion.get().recargo_por_taper, Decimal('2.00'))
        self.assertEqual(Plato.objects.get(nombre='Lomo Saltado').precio, Decimal('9.50'))

    def test_reset_restores_canonical_pricing(self):
        # --reset force-overwrites the canonical price/surcharge values
        # (Menu 13.00, recargo 1.00) regardless of admin edits.
        self._run(reset=True)
        menu = Menu.objects.get(nombre='Menú')
        menu.precio = Decimal('15.00')
        menu.save()
        cfg = Configuracion.get()
        cfg.recargo_por_taper = Decimal('2.00')
        cfg.save()

        self._run(reset=True)

        self.assertEqual(Menu.objects.get(nombre='Menú').precio, Decimal('13.00'))
        self.assertEqual(Configuracion.get().recargo_por_taper, Decimal('1.00'))


class PosViewTotalTest(TestCase):
    """Task 3.1 — pos_view computes `orden.total` via `Orden.computar_total()`:
    a Menu line is priced as a unit, and the "para llevar" taper surcharge is
    applied only when `tipo_servicio='LLEVAR'` (view scenarios: "LLEVAR order
    total includes surcharge", "MESA order total has no surcharge")."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='mozo', password='password123')
        self.client.login(username='mozo', password='password123')
        self.entrada = Categoria.objects.create(nombre='Entrada', orden=1, packable=True)
        self.segundo = Categoria.objects.create(nombre='Segundo', orden=2, packable=True)
        # precio default 13.00
        self.menu = Menu.objects.create(
            categoria_entrada=self.entrada,
            categoria_segundo=self.segundo,
        )

    def _post_orden(self, tipo_servicio):
        items = json.dumps([{'id': self.menu.id, 'tipo': 'menu', 'cantidad': 1, 'nota': '', 'es_para_llevar': (tipo_servicio == 'LLEVAR')}])
        return self.client.post(
            reverse('pos'),
            {
                'items_json': items,
                'tipo_servicio': tipo_servicio,
                'nota_general': '',
            },
        )

    def test_llevar_menu_line_total_includes_surcharge(self):
        response = self._post_orden('LLEVAR')
        self.assertEqual(response.status_code, 302)
        orden = Orden.objects.get()
        detalle = orden.detalles.get()
        # menu line prices as a unit (not the sum of sopa + segundo)
        self.assertEqual(detalle.menu, self.menu)
        self.assertIsNone(detalle.plato)
        self.assertEqual(detalle.precio_unitario, Decimal('13.00'))
        # 13.00 + (2 tapers × 1.00) = 15.00
        self.assertEqual(orden.total, Decimal('15.00'))

    def test_mesa_menu_line_total_has_no_surcharge(self):
        response = self._post_orden('MESA')
        self.assertEqual(response.status_code, 302)
        orden = Orden.objects.get()
        # 13.00 fixed menu price, no taper surcharge on MESA
        self.assertEqual(orden.total, Decimal('13.00'))

    def test_llevar_plato_line_flow_through_computar_total(self):
        # Backward-compatible plato path (no 'tipo' key → defaults to plato):
        # a packable plato line must also be priced via computar_total, so a
        # LLEVAR a-la-carte second incurs its 1-taper surcharge.
        plato = Plato.objects.create(nombre='Lomo Saltado', precio=Decimal('11.00'), categoria=self.segundo)
        items = json.dumps([{'id': plato.id, 'cantidad': 1, 'nota': '', 'es_para_llevar': True}])
        response = self.client.post(
            reverse('pos'),
            {
                'items_json': items,
                'tipo_servicio': 'LLEVAR',
                'nota_general': '',
            },
        )
        self.assertEqual(response.status_code, 302)
        orden = Orden.objects.get()
        detalle = orden.detalles.get()
        self.assertEqual(detalle.plato, plato)
        self.assertIsNone(detalle.menu)
        # 11.00 + (1 taper × 1.00) = 12.00
        self.assertEqual(orden.total, Decimal('12.00'))


class Pr3MenuComboFixesTest(TestCase):
    """PR3 adversarial-review fixes for the Menu sealed-combo wiring.

    Issue 1: kitchen endpoints must not crash on a Menu line (plato=None) —
    `api_cocina_ordenes` must return the menu name and the cocina page must
    render it. Issue 2: inactive Menu/Plato must be rejected at the write
    boundary (404). Issue 3: a malformed payload must not persist an orphan
    PENDIENTE Orden."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='mozo', password='password123')
        self.client.login(username='mozo', password='password123')
        self.entrada = Categoria.objects.create(nombre='Entrada', orden=1, packable=True)
        self.segundo = Categoria.objects.create(nombre='Segundo', orden=2, packable=True)
        # Unique name (not the default "Menú") so template assertions target the
        # order-detail line and not the sidebar navigation "Menú" label.
        self.menu = Menu.objects.create(
            nombre='Menú Sellado Único',
            categoria_entrada=self.entrada,
            categoria_segundo=self.segundo,
        )

    def _post_menu_order(self):
        items = json.dumps([{'id': self.menu.id, 'tipo': 'menu', 'cantidad': 1, 'nota': ''}])
        return self.client.post(
            reverse('pos'),
            {
                'items_json': items,
                'tipo_servicio': 'MESA',
                'nota_general': '',
            },
        )

    # --- Issue 1: kitchen endpoints and Menu lines ---
    def test_api_cocina_ordenes_returns_menu_name_for_menu_line(self):
        # A PENDIENTE order with a Menu line (plato=None) must serialize to the
        # kitchen API with the menu's name, NOT raise AttributeError (HTTP 500).
        self._post_menu_order()
        response = self.client.get(reverse('api_cocina_ordenes'))
        self.assertEqual(response.status_code, 200)
        ordenes = response.json()['ordenes']
        self.assertEqual(len(ordenes), 1)
        detalle = ordenes[0]['detalles'][0]
        self.assertEqual(detalle['plato_nombre'], self.menu.nombre)

    def test_cocina_page_renders_menu_name_for_menu_line(self):
        self._post_menu_order()
        response = self.client.get(reverse('cocina'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.menu.nombre)

    def test_api_cocina_ordenes_returns_plato_name_for_plato_line(self):
        # Triangulation: the fallback must pick the plato name when a plato line
        # is present (never blindly the menu).
        plato = Plato.objects.create(nombre='Lomo Saltado', precio=11.00, categoria=self.segundo)
        items = json.dumps([{'id': plato.id, 'cantidad': 1, 'nota': ''}])
        self.client.post(
            reverse('pos'),
            {
                'items_json': items,
                'tipo_servicio': 'MESA',
                'nota_general': '',
            },
        )
        response = self.client.get(reverse('api_cocina_ordenes'))
        self.assertEqual(response.status_code, 200)
        detalle = response.json()['ordenes'][0]['detalles'][0]
        self.assertEqual(detalle['plato_nombre'], plato.nombre)

    # --- Issue 2: inactive Menu/Plato rejected at write boundary ---
    def test_post_inactive_menu_returns_404(self):
        self.menu.activo = False
        self.menu.save()
        items = json.dumps([{'id': self.menu.id, 'tipo': 'menu', 'cantidad': 1}])
        response = self.client.post(
            reverse('pos'),
            {
                'items_json': items,
                'tipo_servicio': 'MESA',
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Orden.objects.count(), 0)

    def test_post_inactive_plato_returns_404(self):
        plato = Plato.objects.create(nombre='Huevo', precio=1.50)
        plato.activo = False
        plato.save()
        items = json.dumps([{'id': plato.id, 'cantidad': 1}])
        response = self.client.post(
            reverse('pos'),
            {
                'items_json': items,
                'tipo_servicio': 'MESA',
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Orden.objects.count(), 0)

    # --- Issue 3: malformed payload must not persist an orphan Orden ---
    def test_post_invalid_item_id_creates_no_orden(self):
        items = json.dumps([{'id': 999999, 'tipo': 'menu', 'cantidad': 1}])
        response = self.client.post(
            reverse('pos'),
            {
                'items_json': items,
                'tipo_servicio': 'MESA',
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Orden.objects.count(), 0)

    def test_post_invalid_cantidad_creates_no_orden(self):
        # int('abc') raises ValueError BEFORE any Orden row may be persisted.
        items = json.dumps([{'id': self.menu.id, 'tipo': 'menu', 'cantidad': 'abc'}])
        with self.assertRaises(ValueError):
            self.client.post(
                reverse('pos'),
                {
                    'items_json': items,
                    'tipo_servicio': 'MESA',
                },
            )
        self.assertEqual(Orden.objects.count(), 0)


class AdminRegistrationTest(TestCase):
    """Task 3.3 — Menu + Configuracion registered in Django admin and editable
    (scenario: "Admin can manage all catalog entities"). Configuracion remains
    a singleton: not addable, but its recargo value is editable in place."""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(username='admin', password='password123')
        self.client.login(username='admin', password='password123')

    def test_menu_and_configuracion_registered_in_site(self):
        self.assertTrue(dj_admin.site.is_registered(Menu))
        self.assertTrue(dj_admin.site.is_registered(Configuracion))

    def test_menu_add_page_renders_editable_fields(self):
        entrada = Categoria.objects.create(nombre='Entrada', orden=1)
        segundo = Categoria.objects.create(nombre='Segundo', orden=2)
        Menu.objects.create(categoria_entrada=entrada, categoria_segundo=segundo)
        response = self.client.get(reverse('admin:restaurante_menu_add'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="categoria_entrada"')
        self.assertContains(response, 'name="categoria_segundo"')
        self.assertContains(response, 'name="precio"')
        self.assertContains(response, 'name="activo"')

    def test_configuracion_not_addable_but_editable(self):
        cfg = Configuracion.get()
        self.assertEqual(cfg.recargo_por_taper, Decimal('1.00'))
        # singleton: adding a second config row is forbidden
        add_response = self.client.get(reverse('admin:restaurante_configuracion_add'))
        self.assertEqual(add_response.status_code, 403)
        # editing the existing singleton row persists
        change_url = reverse('admin:restaurante_configuracion_change', args=[cfg.id])
        change_response = self.client.post(change_url, {'recargo_por_taper': '2.50', 'modo_envio': 'KITCHEN'})
        self.assertEqual(change_response.status_code, 302)
        cfg.refresh_from_db()
        self.assertEqual(cfg.recargo_por_taper, Decimal('2.50'))

    def test_configuracion_modo_envio_admin_editable(self):
        # APP-CONF-1 admin-editability: the admin change form exposes modo_envio
        # and persists a new value.
        cfg = Configuracion.get()
        change_url = reverse('admin:restaurante_configuracion_change', args=[cfg.id])
        change_response = self.client.post(change_url, {'recargo_por_taper': '1.00', 'modo_envio': 'PRINT'})
        self.assertEqual(change_response.status_code, 302)
        cfg.refresh_from_db()
        self.assertEqual(cfg.modo_envio, 'PRINT')


class PosViewAjaxTest(TestCase):
    """POS-PRINT-1/2: an AJAX POST (X-Requested-With header) must create the
    order through the existing path, fire Pusher 'nueva-orden' at the same
    point, and return ticket JSON. Non-AJAX POSTs keep the redirect behavior."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='mozo', password='password123')
        self.client.login(username='mozo', password='password123')
        cfg = Configuracion.get()
        cfg.modo_envio = 'PRINT'
        cfg.save()
        self.entrada = Categoria.objects.create(nombre='Entrada', orden=1, packable=True)
        self.segundo = Categoria.objects.create(nombre='Segundo', orden=2, packable=True)
        # precio default 13.00
        self.menu = Menu.objects.create(
            categoria_entrada=self.entrada,
            categoria_segundo=self.segundo,
        )
        self.plato = Plato.objects.create(nombre='Lomo Saltado', precio=Decimal('11.00'), categoria=self.segundo)

    def _ajax_post(self, data):
        return self.client.post(reverse('pos'), data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_ajax_valid_cart_returns_json_creates_order_and_fires_pusher(self):
        items = json.dumps([{'id': self.menu.id, 'tipo': 'menu', 'cantidad': 1, 'nota': 'sin cebolla', 'es_para_llevar': True}])
        with patch('restaurante.views.trigger_pusher_event') as mock_pusher:
            response = self._ajax_post({'items_json': items, 'tipo_servicio': 'LLEVAR', 'nota_general': 'Pedido urgente'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        ticket = data['ticket']
        orden = Orden.objects.get()
        self.assertEqual(ticket['orden_id'], orden.id)
        self.assertRegex(ticket['hora_str'], r'^\d{2}:\d{2}$')
        self.assertEqual(ticket['tipo_servicio'], 'LLEVAR')
        self.assertEqual(ticket['mesa_label'], 'PARA LLEVAR')
        self.assertEqual(ticket['nota_general'], 'Pedido urgente')
        self.assertEqual(ticket['total'], '15.00')
        self.assertEqual(len(ticket['detalles']), 1)
        detalle = ticket['detalles'][0]
        self.assertEqual(detalle['nombre'], self.menu.nombre)
        self.assertEqual(detalle['cantidad'], 1)
        self.assertEqual(detalle['nota'], 'sin cebolla')
        self.assertTrue(detalle['es_menu'])
        mock_pusher.assert_called_once_with('nueva-orden', {'orden_id': orden.id})

    def test_llevar_menu_line_shows_both_taper_badges_and_flags(self):
        items = json.dumps([{'id': self.menu.id, 'tipo': 'menu', 'cantidad': 1, 'nota': ''}])
        response = self._ajax_post({'items_json': items, 'tipo_servicio': 'LLEVAR', 'nota_general': ''})
        detalle = response.json()['ticket']['detalles'][0]
        self.assertEqual(detalle['badges'], ['Entrada Táper', 'Segundo Táper'])
        self.assertTrue(detalle['es_menu'])
        self.assertTrue(detalle['entrada_para_llevar'])
        self.assertTrue(detalle['segundo_para_llevar'])
        self.assertTrue(detalle['es_para_llevar'])

    def test_menu_line_one_component_tapered_shows_only_that_badge(self):
        items = json.dumps([{'id': self.menu.id, 'tipo': 'menu', 'cantidad': 1, 'nota': '', 'entrada_para_llevar': True, 'segundo_para_llevar': False}])
        response = self._ajax_post({'items_json': items, 'tipo_servicio': 'MESA', 'nota_general': ''})
        detalle = response.json()['ticket']['detalles'][0]
        self.assertEqual(detalle['badges'], ['Entrada Táper'])
        self.assertTrue(detalle['entrada_para_llevar'])
        self.assertFalse(detalle['segundo_para_llevar'])

    def test_llevar_packable_plato_line_shows_taper_badge(self):
        items = json.dumps([{'id': self.plato.id, 'cantidad': 1, 'nota': '', 'es_para_llevar': True}])
        response = self._ajax_post({'items_json': items, 'tipo_servicio': 'LLEVAR', 'nota_general': ''})
        detalle = response.json()['ticket']['detalles'][0]
        self.assertEqual(detalle['nombre'], self.plato.nombre)
        self.assertEqual(detalle['badges'], ['TÁPER'])
        self.assertFalse(detalle['es_menu'])
        self.assertTrue(detalle['es_para_llevar'])
        self.assertEqual(response.json()['ticket']['total'], '12.00')

    def test_mesa_order_label_and_no_badges(self):
        ambiente = Ambiente.objects.create(nombre='Salón', orden=1)
        mesa = Mesa.objects.create(ambiente=ambiente, numero='Mesa 3', capacidad=4)
        items = json.dumps([{'id': self.plato.id, 'cantidad': 1, 'nota': '', 'es_para_llevar': False}])
        response = self._ajax_post({'items_json': items, 'tipo_servicio': 'MESA', 'mesa_id': str(mesa.id), 'nota_general': ''})
        ticket = response.json()['ticket']
        self.assertEqual(ticket['tipo_servicio'], 'MESA')
        self.assertEqual(ticket['mesa_label'], 'Mesa 3')
        self.assertEqual(ticket['detalles'][0]['badges'], [])
        self.assertEqual(ticket['total'], '11.00')

    def test_mesa_with_plain_number_gets_prefixed_label(self):
        ambiente = Ambiente.objects.create(nombre='Salón', orden=1)
        mesa = Mesa.objects.create(ambiente=ambiente, numero='5', capacidad=4)
        items = json.dumps([{'id': self.plato.id, 'cantidad': 1, 'nota': '', 'es_para_llevar': False}])
        response = self._ajax_post({'items_json': items, 'tipo_servicio': 'MESA', 'mesa_id': str(mesa.id), 'nota_general': ''})
        self.assertEqual(response.json()['ticket']['mesa_label'], 'Mesa 5')

    def test_server_total_includes_non_default_taper_surcharge(self):
        cfg = Configuracion.get()
        cfg.recargo_por_taper = Decimal('2.00')
        cfg.save()
        items = json.dumps([{'id': self.menu.id, 'tipo': 'menu', 'cantidad': 1, 'nota': ''}])
        response = self._ajax_post({'items_json': items, 'tipo_servicio': 'LLEVAR', 'nota_general': ''})
        ticket = response.json()['ticket']
        # 13.00 + (2 tapers × 2.00) = 17.00 — matches Orden.computar_total()
        self.assertEqual(ticket['total'], '17.00')
        self.assertEqual(str(Orden.objects.get().total), '17.00')

    def test_plain_post_in_print_mode_still_redirects(self):
        items = json.dumps([{'id': self.menu.id, 'tipo': 'menu', 'cantidad': 1, 'nota': ''}])
        response = self.client.post(
            reverse('pos'),
            {'items_json': items, 'tipo_servicio': 'MESA', 'nota_general': ''},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(response.get('Content-Type', '').startswith('application/json'))
        self.assertEqual(Orden.objects.count(), 1)

    def test_ajax_empty_cart_creates_no_order(self):
        response = self._ajax_post({'items_json': '[]', 'tipo_servicio': 'LLEVAR', 'nota_general': ''})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Orden.objects.count(), 0)

    def test_ajax_invalid_item_creates_no_order(self):
        items = json.dumps([{'id': 999999, 'tipo': 'menu', 'cantidad': 1}])
        response = self._ajax_post({'items_json': items, 'tipo_servicio': 'MESA'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Orden.objects.count(), 0)


class PosTemplatePrintWiringTest(TestCase):
    """Template-level wiring for the PRINT JS module (POS-PRINT-3/4/5) and the
    minimal PWA manifest (POS-PRINT-3 secure-context requirement). No JS test
    runner exists, so the next available layer is rendered-HTML assertions."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='mozo', password='password123')
        self.client.login(username='mozo', password='password123')

    def test_pos_renders_modo_envio_const(self):
        cfg = Configuracion.get()
        cfg.modo_envio = 'PRINT'
        cfg.save()
        response = self.client.get(reverse('pos'))
        self.assertContains(response, "const MODO_ENVIO = 'PRINT';")

    def test_pos_renders_print_module_functions(self):
        response = self.client.get(reverse('pos'))
        for fn in ('sanitizeText', 'wrap80', 'fetchTicketData', 'buildEscPos', 'connectPrinting', 'enviarOrdenPrint'):
            self.assertContains(response, f'function {fn}')

    def test_pos_renders_print_gate_in_send_handlers(self):
        response = self.client.get(reverse('pos'))
        self.assertContains(response, "MODO_ENVIO === 'PRINT'")

    def test_base_renders_manifest_link(self):
        response = self.client.get(reverse('pos'))
        self.assertContains(response, 'rel="manifest"')
        self.assertContains(response, 'manifest.webmanifest')


class AmbienteAndMesaTest(TestCase):
    """Tests for Ambiente and Mesa models, order table binding, and table status transitions."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='mesero', password='password123')
        self.client.login(username='mesero', password='password123')
        self.ambiente = Ambiente.objects.create(nombre='Salón Principal', orden=1)
        self.mesa = Mesa.objects.create(ambiente=self.ambiente, numero='Mesa 1', capacidad=4)
        self.cat = Categoria.objects.create(nombre='Segundo', orden=1, packable=True)
        self.plato = Plato.objects.create(nombre='Lomo Saltado', precio=11.00, categoria=self.cat)

    def test_crear_orden_con_mesa_cambia_estado_a_ocupada(self):
        items_json = json.dumps([{'id': self.plato.id, 'tipo': 'plato', 'cantidad': 1, 'precio': 11.00, 'es_para_llevar': False, 'nota': ''}])
        response = self.client.post(reverse('pos'), {'tipo_servicio': 'MESA', 'mesa_id': str(self.mesa.id), 'items_json': items_json, 'nota_general': 'Mesa 1'})
        self.assertEqual(response.status_code, 302)
        self.mesa.refresh_from_db()
        self.assertEqual(self.mesa.estado, 'OCUPADA')
        orden = Orden.objects.first()
        self.assertEqual(orden.mesa, self.mesa)

    def test_cobrar_orden_libera_mesa_a_disponible(self):
        orden = Orden.objects.create(tipo_servicio='MESA', mesa=self.mesa, estado='LISTO')
        self.mesa.estado = 'OCUPADA'
        self.mesa.save()

        response = self.client.post(reverse('cobrar_orden', args=[orden.id]), {'metodo_pago': 'EFECTIVO'})
        self.assertEqual(response.status_code, 302)
        self.mesa.refresh_from_db()
        self.assertEqual(self.mesa.estado, 'DISPONIBLE')

    def test_orden_para_llevar_no_requiere_mesa(self):
        items_json = json.dumps([{'id': self.plato.id, 'tipo': 'plato', 'cantidad': 1, 'precio': 11.00, 'es_para_llevar': True, 'nota': ''}])
        response = self.client.post(reverse('pos'), {'tipo_servicio': 'LLEVAR', 'items_json': items_json, 'nota_general': 'Para Llevar'})
        self.assertEqual(response.status_code, 302)
        orden = Orden.objects.first()
        self.assertIsNone(orden.mesa)
        self.assertEqual(orden.tipo_servicio, 'LLEVAR')

    def test_guardar_posiciones_mesas_api(self):
        User.objects.create_superuser(username='admin_pos', password='password123')
        self.client.login(username='admin_pos', password='password123')
        payload = {'mesas': [{'id': self.mesa.id, 'x': 150, 'y': 220}]}
        response = self.client.post(reverse('api_guardar_posiciones_mesas'), data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.mesa.refresh_from_db()
        self.assertEqual(self.mesa.posicion_x, 150)
        self.assertEqual(self.mesa.posicion_y, 220)
