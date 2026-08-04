import base64
import io
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw, ImageFont

from restaurante.models import Ambiente, Categoria, Configuracion, Menu, Mesa, Plato

SEED_AMBIENTES = [
    {
        'nombre': 'Salón Principal',
        'orden': 1,
        'mesas': [
            {'numero': 'Mesa 1', 'capacidad': 4},
            {'numero': 'Mesa 2', 'capacidad': 4},
            {'numero': 'Mesa 3', 'capacidad': 4},
            {'numero': 'Mesa 4', 'capacidad': 6},
            {'numero': 'Mesa 5', 'capacidad': 6},
            {'numero': 'Mesa 6', 'capacidad': 2},
        ]
    },
    {
        'nombre': 'Terraza',
        'orden': 2,
        'mesas': [
            {'numero': 'Mesa 7', 'capacidad': 4},
            {'numero': 'Mesa 8', 'capacidad': 4},
            {'numero': 'Mesa 9', 'capacidad': 2},
            {'numero': 'Mesa 10', 'capacidad': 8},
        ]
    },
]

# ---------------------------------------------------------------------------
# Deterministic seed catalog (docs/contexto/catalogo.md).
# Packability is an intrinsic property of the CATEGORY (design D2): Entrada and
# Segundo pack a "para llevar" taper (packable=True); Añadidos do not
# (packable=False — the model default, set explicitly here for older rows).
#
# Pricing reconciliation policy (design D5 + catalog admin-editability):
#   - A PLAIN (non-`--reset`) run reconciles STRUCTURE only: it creates missing
#     categories/platos/menu, re-parents rows by name, fixes packable flags and
#     category wiring, and fills empty images. It NEVER overwrites an existing
#     Menu.precio, Configuracion.recargo_por_taper, or existing Plato.precio.
#   - `--reset` additionally force-overwrites the canonical seed prices/surcharge.
# ---------------------------------------------------------------------------

SEED_CATEGORIAS = [
    {'nombre': 'Entrada', 'orden': 1, 'packable': True},
    {'nombre': 'Segundo', 'orden': 2, 'packable': True},
    {'nombre': 'Añadidos', 'orden': 3, 'packable': False},
]

SEED_PLATOS = [
    ('Entrada', 'Sopa de Res', Decimal('6.00')),
    ('Segundo', 'Lomo Saltado', Decimal('11.00')),
    ('Segundo', 'Pollo Dorado', Decimal('11.00')),
    ('Segundo', 'Hamburguesa al Plato', Decimal('11.00')),
    ('Segundo', 'Chuleta de Res', Decimal('11.00')),
    ('Segundo', 'Saltado de Mollejas', Decimal('11.00')),
    ('Segundo', 'Hígado Frito', Decimal('11.00')),
    ('Segundo', 'Pollo Broaster', Decimal('11.00')),
    ('Segundo', 'Riñón Saltado', Decimal('11.00')),
    ('Segundo', 'Chuleta de Chancho', Decimal('11.00')),
    ('Segundo', 'Arroz a la Cubana', Decimal('11.00')),
    ('Añadidos', 'Huevo', Decimal('1.50')),
    ('Añadidos', 'Porción de Arroz', Decimal('3.00')),
    ('Añadidos', 'Porción de Papa', Decimal('3.00')),
]

MENU_NOMBRE = 'Menú'
MENU_PRECIO = Decimal('13.00')
RECARGO_POR_TAPER = Decimal('1.00')

# Per-plato placeholder palette (background, accent) reused so seeded images are
# deterministic and visually distinct per dish. Filled only when imagen_base64
# is empty — never overwrites an admin-assigned image.
SEED_PALETTES = {
    'Sopa de Res': ((139, 69, 19), (205, 133, 63)),
    'Lomo Saltado': ((139, 69, 19), (205, 133, 63)),
    'Pollo Dorado': ((218, 165, 32), (255, 215, 0)),
    'Hamburguesa al Plato': ((101, 67, 33), (160, 82, 45)),
    'Chuleta de Res': ((178, 34, 34), (220, 20, 60)),
    'Saltado de Mollejas': ((0, 128, 128), (72, 209, 204)),
    'Hígado Frito': ((72, 61, 139), (123, 104, 238)),
    'Pollo Broaster': ((245, 107, 69), (255, 215, 0)),
    'Riñón Saltado': ((105, 105, 105), (169, 169, 169)),
    'Chuleta de Chancho': ((160, 82, 45), (222, 184, 135)),
    'Arroz a la Cubana': ((34, 139, 34), (144, 238, 144)),
    'Huevo': ((255, 140, 0), (255, 215, 0)),
    'Porción de Arroz': ((245, 245, 220), (211, 211, 211)),
    'Porción de Papa': ((238, 203, 173), (222, 184, 135)),
}


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
    help = 'Sembrar catálogo determinístico, menú sellado y configuración; crear superusuario.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Desactiva el catálogo/menú existente antes de resembrar.',
        )

    def handle(self, *args, **options):
        reset = options['reset']
        self._ensure_superuser()
        self._reconcile_ambientes_y_mesas(reset)
        self._reconcile_categorias(reset)
        self._reconcile_platos(reset)
        self._reconcile_menu(reset)
        self._ensure_configuracion(reset)
        self.stdout.write(self.style.SUCCESS('Semilla completada.'))

    def _reconcile_ambientes_y_mesas(self, reset):
        if reset:
            Ambiente.objects.update(activo=False)
            Mesa.objects.update(activo=False)
        for amb_data in SEED_AMBIENTES:
            amb, _ = Ambiente.objects.get_or_create(
                nombre=amb_data['nombre'],
                defaults={'orden': amb_data['orden']}
            )
            amb.orden = amb_data['orden']
            amb.activo = True
            amb.save()

            for m_data in amb_data['mesas']:
                mesa, _ = Mesa.objects.get_or_create(
                    ambiente=amb,
                    numero=m_data['numero'],
                    defaults={'capacidad': m_data['capacidad']}
                )
                mesa.capacidad = m_data['capacidad']
                mesa.activo = True
                mesa.save()
            self.stdout.write(self.style.SUCCESS(f'Ambiente listo: {amb.nombre} ({len(amb_data["mesas"])} mesas)'))

    def _ensure_superuser(self):
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@restaurante.com', 'admin123')
            self.stdout.write(self.style.SUCCESS('Superusuario creado: admin / admin123'))

    def _reconcile_categorias(self, reset):
        if reset:
            # Soft-deactivate (never .delete()) so existing order rows
            # (DetalleOrden.plato PROTECT) and history survive. See design D5.
            Categoria.objects.update(activo=False)
        for data in SEED_CATEGORIAS:
            cat, _ = Categoria.objects.get_or_create(
                nombre=data['nombre'],
                defaults={'orden': data['orden'], 'packable': data['packable']},
            )
            # Re-run reconciliation: force the canonical flags even on older rows.
            cat.orden = data['orden']
            cat.packable = data['packable']
            cat.activo = True
            cat.save()
            self.stdout.write(self.style.SUCCESS(f"Categoría lista: {cat.nombre}"))

    def _reconcile_platos(self, reset):
        if reset:
            Plato.objects.update(activo=False)
        for cat_nombre, nombre, precio in SEED_PLATOS:
            categoria = Categoria.objects.get(nombre=cat_nombre)
            # Match by name FIRST (regardless of category) so legacy rows from the
            # OLD seed (categoria=None on real-name demo rows) are reused and
            # re-parented instead of being duplicated. Design D5.
            plato = Plato.objects.filter(nombre=nombre).first()
            is_new = plato is None
            if is_new:
                plato = Plato(nombre=nombre)
            # Re-parent to the canonical seed category.
            plato.categoria = categoria
            # Force canonical price only on --reset (or for newly created rows);
            # a plain run preserves admin-edited Plato.precio.
            if reset or is_new:
                plato.precio = precio
            plato.activo = True
            # Fill a placeholder image only when empty (never overwrite admin image).
            if not plato.imagen_base64:
                bg, accent = SEED_PALETTES[nombre]
                plato.imagen_base64 = generar_imagen_demo(nombre, bg, accent)
            plato.save()
            self.stdout.write(self.style.SUCCESS(f'Plato listo: {plato.nombre}'))

    def _reconcile_menu(self, reset):
        if reset:
            Menu.objects.update(activo=False)
        entrada = Categoria.objects.get(nombre='Entrada')
        segundo = Categoria.objects.get(nombre='Segundo')
        menu = Menu.objects.filter(nombre=MENU_NOMBRE).first()
        is_new = menu is None
        if is_new:
            menu = Menu(nombre=MENU_NOMBRE)
        menu.categoria_entrada = entrada
        menu.categoria_segundo = segundo
        # Force canonical price only on --reset (or for a newly created menu);
        # a plain run preserves an admin-edited Menu.precio.
        if reset or is_new:
            menu.precio = MENU_PRECIO
        menu.activo = True
        menu.save()
        self.stdout.write(self.style.SUCCESS(f'Menú listo: {menu.nombre} ({menu.precio})'))

    def _ensure_configuracion(self, reset):
        cfg = Configuracion.get()
        # Force canonical surcharge only on --reset; a plain run preserves an
        # admin-edited recargo_por_taper.
        if reset:
            cfg.recargo_por_taper = RECARGO_POR_TAPER
            cfg.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Configuración lista: recargo por taper {cfg.recargo_por_taper}'
                )
            )
