import base64
import io

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw, ImageFont

from restaurante.models import Plato


def generar_imagen_demo(nombre, color_bg, color_accent):
    """Genera una tarjeta elegante de 400x300 en JPEG Base64 comprimido para pruebas."""
    img = Image.new('RGB', (400, 300), color=color_bg)
    draw = ImageDraw.Draw(img)

    # Dibujar elementos decorativos
    draw.rectangle([20, 20, 380, 280], outline=color_accent, width=4)
    draw.ellipse([140, 70, 260, 190], fill=color_accent)

    # Texto
    try:
        font_title = ImageFont.truetype("arial.ttf", 26)
        font_sub = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    # Título en el centro
    text_bbox = draw.textbbox((0, 0), nombre, font=font_title)
    w = text_bbox[2] - text_bbox[0]
    draw.text(((400 - w) / 2, 215), nombre, fill=(255, 255, 255), font=font_title)

    sub_text = "Especialidad de la Casa"
    sub_bbox = draw.textbbox((0, 0), sub_text, font=font_sub)
    sw = sub_bbox[2] - sub_bbox[0]
    draw.text(((400 - sw) / 2, 250), sub_text, fill=(220, 220, 220), font=font_sub)

    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=75, optimize=True)
    buffer.seek(0)
    encoded = base64.b64encode(buffer.read()).decode('utf-8')
    return f"data:image/jpeg;base64,{encoded}"


class Command(BaseCommand):
    help = 'Poblar datos iniciales, crear superusuario y asignar imágenes de prueba.'

    def handle(self, *args, **options):
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@restaurante.com', 'admin123')
            self.stdout.write(self.style.SUCCESS('Superusuario creado: admin / admin123'))

        platos_iniciales = [
            {'nombre': 'Lomo Saltado', 'precio': 28.00, 'bg': (139, 69, 19), 'accent': (205, 133, 63)},
            {'nombre': 'Ceviche Mixto', 'precio': 32.00, 'bg': (0, 128, 128), 'accent': (72, 209, 204)},
            {'nombre': 'Arroz con Pollo', 'precio': 22.00, 'bg': (34, 139, 34), 'accent': (144, 238, 144)},
            {'nombre': 'Aji de Gallina', 'precio': 24.00, 'bg': (218, 165, 32), 'accent': (255, 215, 0)},
            {'nombre': 'Chicha Morada 1L', 'precio': 10.00, 'bg': (75, 0, 130), 'accent': (147, 112, 219)},
            {'nombre': 'Inca Kola 1.5L', 'precio': 9.00, 'bg': (245, 107, 69), 'accent': (255, 215, 0)},
        ]

        for p in platos_iniciales:
            plato, created = Plato.objects.get_or_create(nombre=p['nombre'], defaults={'precio': p['precio']})
            
            # Asignar imagen Base64 si no tiene una
            if not plato.imagen_base64:
                plato.imagen_base64 = generar_imagen_demo(p['nombre'], p['bg'], p['accent'])
                plato.save()
                self.stdout.write(self.style.SUCCESS(f'Imagen generada y asignada a: {plato.nombre}'))

            if created:
                self.stdout.write(self.style.SUCCESS(f'Plato creado: {plato.nombre}'))
