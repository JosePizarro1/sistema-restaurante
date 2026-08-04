import base64
import io
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.db.models import Count, Sum
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from PIL import Image

from .models import Categoria, DetalleOrden, Menu, Orden, Plato
from .pusher_utils import trigger_pusher_event


def superuser_required(view_func):
    decorator = user_passes_test(
        lambda u: u.is_authenticated and u.is_superuser,
        login_url='/login/'
    )
    return decorator(view_func)

def process_image_to_base64(imagen_file):
    img = Image.open(imagen_file)
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    img.thumbnail((400, 300), Image.LANCZOS)
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=70, optimize=True)
    buffer.seek(0)
    encoded = base64.b64encode(buffer.read()).decode('utf-8')
    return f"data:image/jpeg;base64,{encoded}"

class CustomLoginView(LoginView):
    template_name = 'login.html'

@login_required
def pos_view(request):
    platos = Plato.objects.filter(activo=True)
    if request.method == 'POST':
        items_json = request.POST.get('items_json')
        
        if not items_json:
            messages.error(request, 'Debe agregar al menos un plato a la orden.')
            return redirect('pos')
            
        items = json.loads(items_json)
        if not items:
            messages.error(request, 'La orden no puede estar vacía.')
            return redirect('pos')

        tipo_servicio = request.POST.get('tipo_servicio', 'MESA')
        nota_general = request.POST.get('nota_general', '').strip()

        # Resolve EVERY item (existence, active, cantidad int) BEFORE creating
        # the Orden so a malformed payload raises (Http404/ValueError) before
        # any PENDIENTE row is persisted — no orphan order on partial failure.
        lineas = []
        for item in items:
            # A sealed-combo line is signalled by item['tipo'] == 'menu' and
            # prices as a unit at the Menu's fixed price. Anything else is a
            # plato line (a la carte). Either way exactly one of plato/menu is
            # set, satisfying the DetalleOrden CheckConstraint.
            cantidad = int(item['cantidad'])
            nota = item.get('nota', '').strip()
            es_para_llevar = bool(item.get('es_para_llevar', False))
            if item.get('tipo') == 'menu':
                menu = get_object_or_404(Menu, id=item['id'], activo=True)
                lineas.append({
                    'menu': menu,
                    'precio_unitario': menu.precio,
                    'cantidad': cantidad,
                    'nota': nota,
                    'es_para_llevar': es_para_llevar,
                })
            else:
                plato = get_object_or_404(Plato, id=item['id'], activo=True)
                lineas.append({
                    'plato': plato,
                    'precio_unitario': plato.precio,
                    'cantidad': cantidad,
                    'nota': nota,
                    'es_para_llevar': es_para_llevar,
                })

        orden = Orden.objects.create(
            metodo_pago='PENDIENTE', 
            estado='PENDIENTE',
            tipo_servicio=tipo_servicio,
            nota_general=nota_general
        )

        for linea in lineas:
            DetalleOrden.objects.create(orden=orden, **linea)

        # Total is computed on the model method so the "para llevar" taper
        # surcharge (LLEVAR only) and Menu unit pricing are deterministic and
        # unit-testable, matching the stored `total` DB field contract.
        orden.total = orden.computar_total()
        orden.save()

        trigger_pusher_event('nueva-orden', {'orden_id': orden.id})

        messages.success(request, f'Orden #{orden.id} enviada a cocina con éxito!')
        return redirect('pos')

    ordenes_listas = Orden.objects.filter(estado='LISTO').prefetch_related('detalles__plato', 'detalles__menu')
    categorias = Categoria.objects.filter(activo=True).order_by('orden', 'nombre')
    menus = Menu.objects.filter(activo=True).select_related('categoria_entrada', 'categoria_segundo')
    entradas = Plato.objects.filter(activo=True, categoria__nombre='Entrada')
    segundos = Plato.objects.filter(activo=True, categoria__nombre='Segundo')
    return render(request, 'pos.html', {
        'platos': platos,
        'menus': menus,
        'entradas': entradas,
        'segundos': segundos,
        'ordenes_listas': ordenes_listas,
        'categorias': categorias,
    })

@login_required
def cobrar_orden(request, orden_id):
    orden = get_object_or_404(Orden, id=orden_id)
    if request.method == 'POST':
        metodo_pago = request.POST.get('metodo_pago')
        if metodo_pago in ['EFECTIVO', 'YAPE', 'TRANSFERENCIA']:
            orden.metodo_pago = metodo_pago
            orden.estado = 'PAGADO'
            orden.save()
            trigger_pusher_event('actualizar-cocina', {'orden_id': orden.id, 'nuevo_estado': 'PAGADO'})
            messages.success(request, f'¡Orden #{orden.id} cobrada y cerrada exitosamente con {orden.get_metodo_pago_display()}!')
    return redirect('pos')

@login_required
def cocina_view(request):
    ordenes_pendientes = Orden.objects.filter(estado='PENDIENTE').prefetch_related('detalles__plato', 'detalles__menu')
    return render(request, 'cocina.html', {'ordenes': ordenes_pendientes})

from django.http import JsonResponse


@login_required
def api_cocina_ordenes(request):
    ordenes_pendientes = Orden.objects.filter(estado='PENDIENTE').prefetch_related('detalles__plato', 'detalles__menu').order_by('fecha_creacion')
    data = []
    for orden in ordenes_pendientes:
        detalles = []
        for det in orden.detalles.all():
            # A Menu line has plato=None; resolve the display name safely so a
            # sold Menu doesn't 500 the kitchen feed.
            nombre = det.plato.nombre if det.plato_id else (det.menu.nombre if det.menu_id else '')
            detalles.append({
                'plato_nombre': nombre,
                'cantidad': det.cantidad,
                'nota': det.nota,
                'es_para_llevar': det.es_para_llevar,
            })
        fecha_local = timezone.localtime(orden.fecha_creacion)
        data.append({
            'id': orden.id,
            'fecha_creacion': orden.fecha_creacion.isoformat(),
            'hora_str': fecha_local.strftime('%H:%M'),
            'tipo_servicio': orden.tipo_servicio,
            'nota_general': orden.nota_general,
            'detalles': detalles
        })
    return JsonResponse({'ordenes': data})

@login_required
def cambiar_estado_orden(request, orden_id, nuevo_estado):
    orden = get_object_or_404(Orden, id=orden_id)
    if nuevo_estado in ['LISTO', 'CANCELADO']:
        orden.estado = nuevo_estado
        orden.save()
        trigger_pusher_event('actualizar-cocina', {'orden_id': orden.id, 'nuevo_estado': nuevo_estado})
        if nuevo_estado == 'LISTO':
            messages.success(request, f'¡Orden #{orden.id} marcada como LISTA para entregar y cobrar!')
        else:
            messages.info(request, f'Orden #{orden.id} cancelada.')
    if request.GET.get('ajax') == '1':
        return JsonResponse({'status': 'ok'})
    return redirect('cocina')

import calendar
from datetime import date, timedelta

from django.db.models.functions import TruncDate


@login_required
def reportes_view(request):
    hoy = timezone.localdate()
    
    # Parámetros de filtro por GET
    mes_str = request.GET.get('mes')
    anio_str = request.GET.get('anio')
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')

    usar_rango = bool(fecha_inicio_str and fecha_fin_str)

    if usar_rango:
        try:
            fecha_inicio = parse_date(fecha_inicio_str)
            fecha_fin = parse_date(fecha_fin_str)
            if not fecha_inicio or not fecha_fin:
                raise ValueError
            mes_sel = fecha_inicio.month
            anio_sel = fecha_inicio.year
        except ValueError:
            usar_rango = False
            mes_sel = hoy.month
            anio_sel = hoy.year
            fecha_inicio = date(anio_sel, mes_sel, 1)
            _, num_days = calendar.monthrange(anio_sel, mes_sel)
            fecha_fin = date(anio_sel, mes_sel, num_days)
    else:
        try:
            mes_sel = int(mes_str) if mes_str else hoy.month
            anio_sel = int(anio_str) if anio_str else hoy.year
        except ValueError:
            mes_sel = hoy.month
            anio_sel = hoy.year
        
        fecha_inicio = date(anio_sel, mes_sel, 1)
        _, num_days = calendar.monthrange(anio_sel, mes_sel)
        fecha_fin = date(anio_sel, mes_sel, num_days)

    # Filtrar órdenes cerradas (PAGADO) en el rango seleccionado
    ordenes_periodo = Orden.objects.filter(
        fecha_creacion__date__gte=fecha_inicio,
        fecha_creacion__date__lte=fecha_fin,
        estado='PAGADO'
    )

    total_ventas = ordenes_periodo.aggregate(Sum('total'))['total__sum'] or 0
    ventas_efectivo = ordenes_periodo.filter(metodo_pago='EFECTIVO').aggregate(Sum('total'))['total__sum'] or 0
    ventas_yape = ordenes_periodo.filter(metodo_pago='YAPE').aggregate(Sum('total'))['total__sum'] or 0
    ventas_transferencia = ordenes_periodo.filter(metodo_pago='TRANSFERENCIA').aggregate(Sum('total'))['total__sum'] or 0

    # Platos más vendidos en el periodo
    platos_mas_vendidos = DetalleOrden.objects.filter(
        orden__in=ordenes_periodo
    ).values('plato__nombre').annotate(total_cantidad=Sum('cantidad')).order_by('-total_cantidad')[:5]

    # Agrupación diaria para el gráfico de líneas
    ventas_diarias_qs = ordenes_periodo.annotate(dia=TruncDate('fecha_creacion')) \
        .values('dia') \
        .annotate(total_dia=Sum('total'))

    ventas_dict = {item['dia']: float(item['total_dia']) for item in ventas_diarias_qs}

    # Generar secuencia de días completa para línea continua
    labels_dias = []
    data_ventas = []
    
    curr = fecha_inicio
    while curr <= fecha_fin:
        labels_dias.append(curr.strftime('%d/%m'))
        data_ventas.append(ventas_dict.get(curr, 0.0))
        curr += timedelta(days=1)

    meses_nombres = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
    ]
    anios_disponibles = list(range(hoy.year - 2, hoy.year + 2))

    context = {
        'total_ventas': total_ventas,
        'ventas_efectivo': ventas_efectivo,
        'ventas_yape': ventas_yape,
        'ventas_transferencia': ventas_transferencia,
        'platos_mas_vendidos': platos_mas_vendidos,
        'labels_dias_json': json.dumps(labels_dias),
        'data_ventas_json': json.dumps(data_ventas),
        'mes_sel': mes_sel,
        'anio_sel': anio_sel,
        'fecha_inicio_str': fecha_inicio.strftime('%Y-%m-%d'),
        'fecha_fin_str': fecha_fin.strftime('%Y-%m-%d'),
        'usar_rango': usar_rango,
        'meses_nombres': meses_nombres,
        'anios_disponibles': anios_disponibles,
    }
    return render(request, 'reportes.html', context)



# ==========================================
# MÓDULO CRUD DE PLATOS (SOLO SUPERUSUARIOS)
# ==========================================

@superuser_required
def platos_list_view(request):
    platos = Plato.objects.all().order_by('-activo', 'nombre')
    return render(request, 'platos/lista.html', {'platos': platos})

@superuser_required
def plato_create_view(request):
    categorias = Categoria.objects.all().order_by('orden', 'nombre')
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        precio = request.POST.get('precio', '0').strip()
        categoria_id = request.POST.get('categoria')
        activo = request.POST.get('activo') == 'on'
        imagen_file = request.FILES.get('imagen')

        if not nombre or not precio:
            messages.error(request, 'El nombre y el precio son requeridos.')
            return render(request, 'platos/form.html', {'categorias': categorias, 'titulo': 'Nuevo Plato'})

        categoria = Categoria.objects.filter(id=categoria_id).first() if categoria_id else None
        plato = Plato(nombre=nombre, precio=precio, categoria=categoria, activo=activo)

        if imagen_file:
            try:
                plato.imagen_base64 = process_image_to_base64(imagen_file)
            except (ValueError, OSError) as e:
                messages.error(request, f'Error al procesar la imagen: {e}')
                return render(request, 'platos/form.html', {'categorias': categorias, 'titulo': 'Nuevo Plato'})

        plato.save()
        messages.success(request, f'¡Plato "{plato.nombre}" creado exitosamente!')
        return redirect('platos_list')

    return render(request, 'platos/form.html', {'categorias': categorias, 'titulo': 'Nuevo Plato'})

@superuser_required
def plato_edit_view(request, plato_id):
    plato = get_object_or_404(Plato, id=plato_id)
    categorias = Categoria.objects.all().order_by('orden', 'nombre')
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        precio = request.POST.get('precio', '0').strip()
        categoria_id = request.POST.get('categoria')
        activo = request.POST.get('activo') == 'on'
        imagen_file = request.FILES.get('imagen')

        if not nombre or not precio:
            messages.error(request, 'El nombre y el precio son requeridos.')
            return render(request, 'platos/form.html', {'plato': plato, 'categorias': categorias, 'titulo': f'Editar {plato.nombre}'})

        categoria = Categoria.objects.filter(id=categoria_id).first() if categoria_id else None
        plato.nombre = nombre
        plato.precio = precio
        plato.categoria = categoria
        plato.activo = activo

        if imagen_file:
            try:
                plato.imagen_base64 = process_image_to_base64(imagen_file)
            except (ValueError, OSError) as e:
                messages.error(request, f'Error al procesar la imagen: {e}')
                return render(request, 'platos/form.html', {'plato': plato, 'categorias': categorias, 'titulo': f'Editar {plato.nombre}'})

        plato.save()
        messages.success(request, f'¡Plato "{plato.nombre}" actualizado exitosamente!')
        return redirect('platos_list')

    return render(request, 'platos/form.html', {'plato': plato, 'categorias': categorias, 'titulo': f'Editar {plato.nombre}'})

from django.views.decorators.http import require_POST


@superuser_required
@require_POST
def plato_toggle_status_view(request, plato_id):
    plato = get_object_or_404(Plato, id=plato_id)
    plato.activo = not plato.activo
    plato.save()
    estado_str = "activado" if plato.activo else "desactivado"
    messages.success(request, f'Plato "{plato.nombre}" {estado_str}.')
    return redirect('platos_list')

@superuser_required
@require_POST
def plato_delete_view(request, plato_id):
    plato = get_object_or_404(Plato, id=plato_id)
    nombre = plato.nombre
    try:
        plato.delete()
        messages.success(request, f'Plato "{nombre}" eliminado.')
    except ProtectedError:
        # Si tiene órdenes asociadas
        plato.activo = False
        plato.save()
        messages.warning(request, f'El plato "{nombre}" tiene historial de ventas, por lo que fue desactivado en lugar de eliminado.')
    return redirect('platos_list')


# ==========================================
# MÓDULO CRUD DE CATEGORÍAS (SUPERUSUARIOS)
# ==========================================

@superuser_required
def categorias_list_view(request):
    categorias = Categoria.objects.annotate(total_platos=Count('platos')).order_by('orden', 'nombre')
    return render(request, 'categorias/lista.html', {'categorias': categorias})

@superuser_required
def categoria_create_view(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        orden = request.POST.get('orden', '0').strip()
        activo = request.POST.get('activo') == 'on'

        if not nombre:
            messages.error(request, 'El nombre de la categoría es requerido.')
            return render(request, 'categorias/form.html', {'titulo': 'Nueva Categoría'})

        try:
            Categoria.objects.create(nombre=nombre, orden=int(orden or 0), activo=activo)
            messages.success(request, f'¡Categoría "{nombre}" creada exitosamente!')
            return redirect('categorias_list')
        except Exception as e:  # noqa: BLE001
            messages.error(request, f'Error al crear la categoría: {e}')
            return render(request, 'categorias/form.html', {'titulo': 'Nueva Categoría'})

    return render(request, 'categorias/form.html', {'titulo': 'Nueva Categoría'})

@superuser_required
def categoria_edit_view(request, categoria_id):
    categoria = get_object_or_404(Categoria, id=categoria_id)
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        orden = request.POST.get('orden', '0').strip()
        activo = request.POST.get('activo') == 'on'

        if not nombre:
            messages.error(request, 'El nombre de la categoría es requerido.')
            return render(request, 'categorias/form.html', {'categoria': categoria, 'titulo': f'Editar {categoria.nombre}'})

        try:
            categoria.nombre = nombre
            categoria.orden = int(orden or 0)
            categoria.activo = activo
            categoria.save()
            messages.success(request, f'¡Categoría "{nombre}" actualizada exitosamente!')
            return redirect('categorias_list')
        except Exception as e:  # noqa: BLE001
            messages.error(request, f'Error al actualizar la categoría: {e}')
            return render(request, 'categorias/form.html', {'categoria': categoria, 'titulo': f'Editar {categoria.nombre}'})

    return render(request, 'categorias/form.html', {'categoria': categoria, 'titulo': f'Editar {categoria.nombre}'})

@superuser_required
@require_POST
def categoria_delete_view(request, categoria_id):
    categoria = get_object_or_404(Categoria, id=categoria_id)
    nombre = categoria.nombre
    categoria.delete()
    messages.success(request, f'Categoría "{nombre}" eliminada exitosamente.')
    return redirect('categorias_list')


