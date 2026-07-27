from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from restaurante.models import Plato

class Command(BaseCommand):
    help = 'Poblar datos iniciales y crear superusuario'

    def handle(self, *args, **options):
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@restaurante.com', 'admin123')
            self.stdout.write(self.style.SUCCESS('Superusuario creado: admin / admin123'))

        platos_iniciales = [
            {'nombre': 'Lomo Saltado', 'precio': 28.00},
            {'nombre': 'Ceviche Mixto', 'precio': 32.00},
            {'nombre': 'Arroz con Pollo', 'precio': 22.00},
            {'nombre': 'Aji de Gallina', 'precio': 24.00},
            {'nombre': 'Chicha Morada 1L', 'precio': 10.00},
            {'nombre': 'Inca Kola 1.5L', 'precio': 9.00},
        ]

        for p in platos_iniciales:
            plato, created = Plato.objects.get_or_create(nombre=p['nombre'], defaults={'precio': p['precio']})
            if created:
                self.stdout.write(self.style.SUCCESS(f'Plato creado: {plato.nombre}'))
