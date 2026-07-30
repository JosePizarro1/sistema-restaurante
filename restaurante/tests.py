from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from .models import Categoria, DetalleOrden, Orden, Plato


class CategoriaModelTest(TestCase):
    def setUp(self):
        self.cat1 = Categoria.objects.create(nombre="Entradas", orden=1)
        self.cat2 = Categoria.objects.create(nombre="Bebidas", orden=2)

    def test_categoria_creation(self):
        self.assertEqual(self.cat1.nombre, "Entradas")
        self.assertEqual(str(self.cat1), "Entradas")
        self.assertTrue(self.cat1.activo)

    def test_categoria_ordering(self):
        categorias = list(Categoria.objects.all())
        self.assertEqual(categorias, [self.cat1, self.cat2])


class PlatoModelTest(TestCase):
    def setUp(self):
        self.cat = Categoria.objects.create(nombre="Picantería Arequipeña", orden=1)
        self.plato = Plato.objects.create(
            nombre="Rocoto Relleno",
            precio=25.50,
            categoria=self.cat
        )

    def test_plato_creation(self):
        self.assertEqual(self.plato.nombre, "Rocoto Relleno")
        self.assertEqual(self.plato.categoria, self.cat)
        self.assertEqual(str(self.plato), "Rocoto Relleno - S/. 25.5")


class OrdenModelTest(TestCase):
    def setUp(self):
        self.plato = Plato.objects.create(nombre="Chupe de Camarones", precio=35.00)
        self.orden = Orden.objects.create(metodo_pago='PENDIENTE', estado='PENDIENTE', total=70.00)
        self.detalle = DetalleOrden.objects.create(
            orden=self.orden,
            plato=self.plato,
            cantidad=2,
            precio_unitario=35.00
        )

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


class CategoriaCRUDTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(username='admin', password='password123')
        self.client.login(username='admin', password='password123')

    def test_categorias_list_view(self):
        Categoria.objects.create(nombre="Postres", orden=1)
        response = self.client.get(reverse('categorias_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Postres")

    def test_categoria_create_view(self):
        response = self.client.post(reverse('categoria_create'), {
            'nombre': 'Jugos Naturales',
            'orden': 3,
            'activo': 'on'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Categoria.objects.filter(nombre='Jugos Naturales').exists())

    def test_categoria_edit_view(self):
        cat = Categoria.objects.create(nombre="Antigua", orden=1)
        response = self.client.post(reverse('categoria_edit', args=[cat.id]), {
            'nombre': 'Editada',
            'orden': 5,
            'activo': 'on'
        })
        self.assertEqual(response.status_code, 302)
        cat.refresh_from_db()
        self.assertEqual(cat.nombre, 'Editada')

    def test_categoria_delete_view(self):
        cat = Categoria.objects.create(nombre="Para Borrar", orden=1)
        response = self.client.post(reverse('categoria_delete', args=[cat.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Categoria.objects.filter(id=cat.id).exists())
