import base64
import calendar
import io
import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.db.models import Count, Sum
from django.db.models.deletion import ProtectedError
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST
from PIL import Image

from .models import Ambiente, Categoria, Configuracion, DetalleOrden, Menu, Mesa, Orden, Plato
from .pusher_utils import trigger_pusher_event


def superuser_required(view_func):
    decorator = user_passes_test(lambda u: u.is_authenticated and u.is_superuser, login_url='/login/')
    return decorator(view_func)


@superuser_required
def configuracion_view(request):
    """Superuser settings page: toggle the order delivery mode (KITCHEN screen
    vs PRINT pre-comanda). Validates the choice; invalid values are rejected
    with an error message and the stored field stays unchanged."""
    configuracion = Configuracion.get()
    if request.method == 'POST':
        modo_envio = request.POST.get('modo_envio')
        if modo_envio in dict(Configuracion.MODO_ENVIO_CHOICES):
            configuracion.modo_envio = modo_envio
            configuracion.save()
            messages.success(request, f'Modo de envío actualizado a "{configuracion.get_modo_envio_display()}".')
            return redirect('configuracion')
        messages.error(request, 'Valor de modo de envío no válido.')
    return render(request, 'configuracion.html', {'configuracion': configuracion})


def _ticket_data(orden):
    """Builds the pre-comanda ticket JSON for a freshly created order.

    Badges mirror the kitchen wording: menu lines show 'Entrada Táper' /
    'Segundo Táper' per tapered component; packable plato lines show 'TÁPER';
    mesa orders show none. `total` is the server-computed Decimal rendered as
    a string so the 80mm printer receives exact cents (matches orden.total)."""
    detalles = []
    for det in orden.detalles.select_related('plato__categoria', 'menu').all():
        badges = []
        if det.menu_id:
            nombre = det.menu.nombre
            if det.entrada_para_llevar:
                badges.append('Entrada Táper')
            if det.segundo_para_llevar:
                badges.append('Segundo Táper')
        elif det.plato_id:
            nombre = det.plato.nombre
            if det.es_para_llevar and det.plato.categoria_id and det.plato.categoria.packable:
                badges.append('TÁPER')
        else:
            nombre = ''
        detalles.append(
            {
                'nombre': nombre,
                'cantidad': det.cantidad,
                'nota': det.nota,
                'es_menu': det.menu_id is not None,
                'es_para_llevar': det.es_para_llevar,
                'entrada_para_llevar': det.entrada_para_llevar,
                'segundo_para_llevar': det.segundo_para_llevar,
                'badges': badges,
            }
        )

    if orden.tipo_servicio == 'MESA' and orden.mesa_id:
        numero = orden.mesa.numero
        mesa_label = numero if str(numero).lower().startswith('mesa') else f'Mesa {numero}'
    else:
        mesa_label = 'PARA LLEVAR'

    return {
        'orden_id': orden.id,
        'hora_str': timezone.localtime(orden.fecha_creacion).strftime('%H:%M'),
        'tipo_servicio': orden.tipo_servicio,
        'mesa_label': mesa_label,
        'nota_general': orden.nota_general,
        'detalles': detalles,
        'total': str(orden.total),
    }


def process_image_to_base64(imagen_file):
    img = Image.open(imagen_file)
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    img.thumbnail((400, 300), Image.LANCZOS)
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=70, optimize=True)
    buffer.seek(0)
    encoded = base64.b64encode(buffer.read()).decode('utf-8')
    return f'data:image/jpeg;base64,{encoded}'


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
            es_para_llevar = bool(item.get('es_para_llevar', False)) or (tipo_servicio == 'LLEVAR')
            if item.get('tipo') == 'menu':
                menu = get_object_or_404(Menu, id=item['id'], activo=True)
                entrada_llevar = bool(item.get('entrada_para_llevar', False))
                segundo_llevar = bool(item.get('segundo_para_llevar', False))
                # If order level is LLEVAR or item es_para_llevar is True and component flags are unset, default both to True
                if (tipo_servicio == 'LLEVAR' or es_para_llevar) and not entrada_llevar and not segundo_llevar:
                    entrada_llevar = True
                    segundo_llevar = True
                lineas.append(
                    {
                        'menu': menu,
                        'precio_unitario': menu.precio,
                        'cantidad': cantidad,
                        'nota': nota,
                        'es_para_llevar': (entrada_llevar or segundo_llevar),
                        'entrada_para_llevar': entrada_llevar,
                        'segundo_para_llevar': segundo_llevar,
                    }
                )
            else:
                plato = get_object_or_404(Plato, id=item['id'], activo=True)
                lineas.append(
                    {
                        'plato': plato,
                        'precio_unitario': plato.precio,
                        'cantidad': cantidad,
                        'nota': nota,
                        'es_para_llevar': es_para_llevar,
                    }
                )

        mesa_id = request.POST.get('mesa_id')
        mesa = None
        if tipo_servicio == 'MESA' and mesa_id:
            mesa = Mesa.objects.filter(id=mesa_id, activo=True).first()

        orden = Orden.objects.create(
            metodo_pago='PENDIENTE',
            estado='PENDIENTE',
            tipo_servicio=tipo_servicio,
            nota_general=nota_general,
            mesa=mesa,
        )

        if mesa:
            mesa.estado = 'OCUPADA'
            mesa.save()

        for linea in lineas:
            DetalleOrden.objects.create(orden=orden, **linea)

        # Total is computed on the model method so the "para llevar" taper
        # surcharge (LLEVAR only) and Menu unit pricing are deterministic and
        # unit-testable, matching the stored `total` DB field contract.
        orden.total = orden.computar_total()
        orden.save()

        trigger_pusher_event('nueva-orden', {'orden_id': orden.id})

        # PRINT mode: the browser POSTs via fetch with X-Requested-With and
        # expects ticket JSON to build the ESC/POS pre-comanda. The header is
        # the only gate — KITCHEN mode never sends it (POS-PRINT-5), and a
        # plain form POST keeps the current messages + redirect behavior.
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'ok', 'ticket': _ticket_data(orden)})

        messages.success(request, f'Orden #{orden.id} enviada a cocina con éxito!')
        return redirect('pos')

    ambientes = Ambiente.objects.filter(activo=True).prefetch_related('mesas')
    platos = Plato.objects.filter(activo=True).select_related('categoria')
    entradas = [p for p in platos if p.categoria and p.categoria.nombre == 'Entrada']
    segundos = [p for p in platos if p.categoria and p.categoria.nombre == 'Segundo']
    ordenes_listas = Orden.objects.filter(estado='LISTO').select_related('mesa').prefetch_related('detalles__plato', 'detalles__menu')
    categorias = Categoria.objects.filter(activo=True).order_by('orden', 'nombre')
    menus = Menu.objects.filter(activo=True).select_related('categoria_entrada', 'categoria_segundo')
    configuracion = Configuracion.get()
    return render(
        request,
        'pos.html',
        {
            'ambientes': ambientes,
            'platos': platos,
            'menus': menus,
            'entradas': entradas,
            'segundos': segundos,
            'ordenes_listas': ordenes_listas,
            'categorias': categorias,
            'configuracion': configuracion,
            'recargo_taper': configuracion.recargo_por_taper,
        },
    )


@login_required
def cobrar_orden(request, orden_id):
    orden = get_object_or_404(Orden, id=orden_id)
    if request.method == 'POST':
        metodo_pago = request.POST.get('metodo_pago')
        if metodo_pago in ['EFECTIVO', 'YAPE', 'TRANSFERENCIA']:
            orden.metodo_pago = metodo_pago
            orden.estado = 'PAGADO'
            orden.save()
            if orden.mesa:
                ordenes_activas = Orden.objects.filter(mesa=orden.mesa, estado__in=['PENDIENTE', 'LISTO']).exclude(id=orden.id).exists()
                if not ordenes_activas:
                    orden.mesa.estado = 'DISPONIBLE'
                    orden.mesa.save()
            trigger_pusher_event('actualizar-cocina', {'orden_id': orden.id, 'nuevo_estado': 'PAGADO'})
            messages.success(request, f'¡Orden #{orden.id} cobrada y cerrada exitosamente con {orden.get_metodo_pago_display()}!')
    return redirect('pos')


@login_required
def cocina_view(request):
    configuracion = Configuracion.get()
    if configuracion.modo_envio == 'PRINT':
        # Modo impresión: las comandas se imprimen en el POS y se entregan en
        # papel; la pantalla de cocina queda como respaldo pero sin listar
        # órdenes (nadie la marca LISTO/CANCELADO en este modo).
        ordenes_pendientes = Orden.objects.none()
    else:
        ordenes_pendientes = Orden.objects.filter(estado='PENDIENTE').prefetch_related('detalles__plato', 'detalles__menu')
    return render(request, 'cocina.html', {'ordenes': ordenes_pendientes, 'configuracion': configuracion})


@login_required
def api_cocina_ordenes(request):
    if Configuracion.get().modo_envio == 'PRINT':
        return JsonResponse({'ordenes': []})
    ordenes_pendientes = Orden.objects.filter(estado='PENDIENTE').prefetch_related('detalles__plato', 'detalles__menu').order_by('fecha_creacion')
    data = []
    for orden in ordenes_pendientes:
        detalles = []
        for det in orden.detalles.all():
            # A Menu line has plato=None; resolve the display name safely so a
            # sold Menu doesn't 500 the kitchen feed.
            nombre = det.plato.nombre if det.plato_id else (det.menu.nombre if det.menu_id else '')
            detalles.append(
                {
                    'plato_nombre': nombre,
                    'cantidad': det.cantidad,
                    'nota': det.nota,
                    'es_menu': det.menu_id is not None,
                    'es_para_llevar': det.es_para_llevar,
                    'entrada_para_llevar': det.entrada_para_llevar,
                    'segundo_para_llevar': det.segundo_para_llevar,
                }
            )
        fecha_local = timezone.localtime(orden.fecha_creacion)
        data.append(
            {
                'id': orden.id,
                'fecha_creacion': orden.fecha_creacion.isoformat(),
                'hora_str': fecha_local.strftime('%H:%M'),
                'tipo_servicio': orden.tipo_servicio,
                'nota_general': orden.nota_general,
                'detalles': detalles,
            }
        )
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
    ordenes_periodo = Orden.objects.filter(fecha_creacion__date__gte=fecha_inicio, fecha_creacion__date__lte=fecha_fin, estado='PAGADO')

    recargo_taper_unitario = Configuracion.get().recargo_por_taper
    detalles_periodo = DetalleOrden.objects.filter(orden__in=ordenes_periodo).select_related('plato__categoria', 'menu', 'orden')

    total_ventas = ordenes_periodo.aggregate(Sum('total'))['total__sum'] or Decimal('0.00')
    ventas_efectivo = ordenes_periodo.filter(metodo_pago='EFECTIVO').aggregate(Sum('total'))['total__sum'] or Decimal('0.00')
    ventas_yape = ordenes_periodo.filter(metodo_pago='YAPE').aggregate(Sum('total'))['total__sum'] or Decimal('0.00')
    ventas_transferencia = ordenes_periodo.filter(metodo_pago='TRANSFERENCIA').aggregate(Sum('total'))['total__sum'] or Decimal('0.00')

    # Métricas de Táper y Envasado
    total_tapers = sum(d.taper_count() for d in detalles_periodo)
    monto_tapers = Decimal(str(total_tapers)) * recargo_taper_unitario
    subtotal_consumo = total_ventas - monto_tapers

    # Servicio MESA vs LLEVAR
    ventas_mesa = ordenes_periodo.filter(tipo_servicio='MESA').aggregate(Sum('total'))['total__sum'] or Decimal('0.00')
    ventas_llevar = ordenes_periodo.filter(tipo_servicio='LLEVAR').aggregate(Sum('total'))['total__sum'] or Decimal('0.00')
    conteo_mesa = ordenes_periodo.filter(tipo_servicio='MESA').count()
    conteo_llevar = ordenes_periodo.filter(tipo_servicio='LLEVAR').count()
    total_ordenes_count = ordenes_periodo.count()
    ticket_promedio = (total_ventas / Decimal(str(total_ordenes_count))) if total_ordenes_count > 0 else Decimal('0.00')

    # Platos a la carta más vendidos
    platos_mas_vendidos = detalles_periodo.filter(plato__isnull=False).values('plato__nombre').annotate(total_cantidad=Sum('cantidad')).order_by('-total_cantidad')[:5]

    # Menús Combo más vendidos
    menus_mas_vendidos = detalles_periodo.filter(menu__isnull=False).values('menu__nombre').annotate(total_cantidad=Sum('cantidad')).order_by('-total_cantidad')[:5]

    # Agrupación diaria para el gráfico de líneas
    ventas_diarias_qs = ordenes_periodo.annotate(dia=TruncDate('fecha_creacion')).values('dia').annotate(total_dia=Sum('total'))

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
        (1, 'Enero'),
        (2, 'Febrero'),
        (3, 'Marzo'),
        (4, 'Abril'),
        (5, 'Mayo'),
        (6, 'Junio'),
        (7, 'Julio'),
        (8, 'Agosto'),
        (9, 'Septiembre'),
        (10, 'Octubre'),
        (11, 'Noviembre'),
        (12, 'Diciembre'),
    ]
    anios_disponibles = list(range(hoy.year - 2, hoy.year + 2))

    context = {
        'total_ventas': total_ventas,
        'subtotal_consumo': subtotal_consumo,
        'total_tapers': total_tapers,
        'monto_tapers': monto_tapers,
        'recargo_taper_unitario': recargo_taper_unitario,
        'ventas_efectivo': ventas_efectivo,
        'ventas_yape': ventas_yape,
        'ventas_transferencia': ventas_transferencia,
        'ventas_mesa': ventas_mesa,
        'ventas_llevar': ventas_llevar,
        'conteo_mesa': conteo_mesa,
        'conteo_llevar': conteo_llevar,
        'total_ordenes_count': total_ordenes_count,
        'ticket_promedio': ticket_promedio,
        'platos_mas_vendidos': platos_mas_vendidos,
        'menus_mas_vendidos': menus_mas_vendidos,
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


@superuser_required
@require_POST
def plato_toggle_status_view(request, plato_id):
    plato = get_object_or_404(Plato, id=plato_id)
    plato.activo = not plato.activo
    plato.save()
    estado_str = 'activado' if plato.activo else 'desactivado'
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


@superuser_required
def mesas_configuracion_view(request):
    ambientes = Ambiente.objects.filter(activo=True).prefetch_related('mesas')
    return render(request, 'mesas/configuracion.html', {'ambientes': ambientes})


@superuser_required
@require_POST
def api_guardar_posiciones_mesas(request):
    try:
        data = json.loads(request.body)
        for item in data.get('mesas', []):
            mesa_id = item.get('id')
            x = item.get('x', 0)
            y = item.get('y', 0)
            Mesa.objects.filter(id=mesa_id).update(posicion_x=x, posicion_y=y)
        return JsonResponse({'status': 'ok'})
    except Exception as e:  # noqa: BLE001
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@superuser_required
@require_POST
def mesa_create_view(request):
    ambiente_id = request.POST.get('ambiente_id')
    numero = request.POST.get('numero', '').strip()
    capacidad = request.POST.get('capacidad', '4').strip()
    forma = request.POST.get('forma', 'RECTANGULO')

    if ambiente_id and numero:
        ambiente = get_object_or_404(Ambiente, id=ambiente_id)
        Mesa.objects.create(
            ambiente=ambiente,
            numero=numero,
            capacidad=int(capacidad or 4),
            forma=forma,
            posicion_x=40,
            posicion_y=40,
        )
        messages.success(request, f'Mesa "{numero}" creada en {ambiente.nombre}.')
    return redirect('mesas_configuracion')


@superuser_required
@require_POST
def mesa_delete_view(request, mesa_id):
    mesa = get_object_or_404(Mesa, id=mesa_id)
    numero = mesa.numero
    mesa.delete()
    messages.success(request, f'Mesa "{numero}" eliminada.')
    return redirect('mesas_configuracion')


@superuser_required
@require_POST
def ambiente_create_view(request):
    nombre = request.POST.get('nombre', '').strip()
    if nombre:
        orden = Ambiente.objects.count() + 1
        Ambiente.objects.create(nombre=nombre, orden=orden)
        messages.success(request, f'Ambiente "{nombre}" creado con éxito.')
    return redirect('mesas_configuracion')


@superuser_required
@require_POST
def ambiente_edit_view(request, ambiente_id):
    ambiente = get_object_or_404(Ambiente, id=ambiente_id)
    nombre = request.POST.get('nombre', '').strip()
    if nombre:
        ambiente.nombre = nombre
        ambiente.save()
        messages.success(request, f'Ambiente actualizado a "{nombre}".')
    return redirect('mesas_configuracion')


@superuser_required
@require_POST
def ambiente_delete_view(request, ambiente_id):
    ambiente = get_object_or_404(Ambiente, id=ambiente_id)
    nombre = ambiente.nombre
    ambiente.delete()
    messages.success(request, f'Ambiente "{nombre}" y sus mesas fueron eliminados.')
    return redirect('mesas_configuracion')
