from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone
from .models import Plato, Orden, DetalleOrden
import json
import io
import base64
from PIL import Image

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

        orden = Orden.objects.create(
            metodo_pago='PENDIENTE', 
            estado='PENDIENTE',
            tipo_servicio=tipo_servicio,
            nota_general=nota_general
        )
        total = 0

        for item in items:
            plato = get_object_or_404(Plato, id=item['id'])
            cantidad = int(item['cantidad'])
            subtotal = plato.precio * cantidad
            total += subtotal
            DetalleOrden.objects.create(
                orden=orden,
                plato=plato,
                cantidad=cantidad,
                precio_unitario=plato.precio,
                nota=item.get('nota', '').strip(),
                es_para_llevar=bool(item.get('es_para_llevar', False))
            )

        orden.total = total
        orden.save()

        messages.success(request, f'Orden #{orden.id} enviada a cocina con éxito!')
        return redirect('pos')

    ordenes_listas = Orden.objects.filter(estado='LISTO').prefetch_related('detalles__plato')
    return render(request, 'pos.html', {'platos': platos, 'ordenes_listas': ordenes_listas})

@login_required
def cobrar_orden(request, orden_id):
    orden = get_object_or_404(Orden, id=orden_id)
    if request.method == 'POST':
        metodo_pago = request.POST.get('metodo_pago')
        if metodo_pago in ['EFECTIVO', 'YAPE', 'TRANSFERENCIA']:
            orden.metodo_pago = metodo_pago
            orden.estado = 'PAGADO'
            orden.save()
            messages.success(request, f'¡Orden #{orden.id} cobrada y cerrada exitosamente con {orden.get_metodo_pago_display()}!')
    return redirect('pos')

@login_required
def cocina_view(request):
    ordenes_pendientes = Orden.objects.filter(estado='PENDIENTE').prefetch_related('detalles__plato')
    return render(request, 'cocina.html', {'ordenes': ordenes_pendientes})

from django.http import JsonResponse

@login_required
def api_cocina_ordenes(request):
    ordenes_pendientes = Orden.objects.filter(estado='PENDIENTE').prefetch_related('detalles__plato').order_by('fecha_creacion')
    data = []
    for orden in ordenes_pendientes:
        detalles = []
        for det in orden.detalles.all():
            detalles.append({
                'plato_nombre': det.plato.nombre,
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
        if nuevo_estado == 'LISTO':
            messages.success(request, f'¡Orden #{orden.id} marcada como LISTA para entregar y cobrar!')
        else:
            messages.info(request, f'Orden #{orden.id} cancelada.')
    return redirect('cocina')

import calendar
from datetime import datetime, date, timedelta
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
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
            fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
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
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        precio = request.POST.get('precio', '0').strip()
        activo = request.POST.get('activo') == 'on'
        imagen_file = request.FILES.get('imagen')

        if not nombre or not precio:
            messages.error(request, 'El nombre y el precio son requeridos.')
            return render(request, 'platos/form.html', {'titulo': 'Nuevo Plato'})

        plato = Plato(nombre=nombre, precio=precio, activo=activo)

        if imagen_file:
            try:
                plato.imagen_base64 = process_image_to_base64(imagen_file)
            except Exception as e:
                messages.error(request, f'Error al procesar la imagen: {e}')
                return render(request, 'platos/form.html', {'titulo': 'Nuevo Plato'})

        plato.save()
        messages.success(request, f'¡Plato "{plato.nombre}" creado exitosamente!')
        return redirect('platos_list')

    return render(request, 'platos/form.html', {'titulo': 'Nuevo Plato'})

@superuser_required
def plato_edit_view(request, plato_id):
    plato = get_object_or_404(Plato, id=plato_id)
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        precio = request.POST.get('precio', '0').strip()
        activo = request.POST.get('activo') == 'on'
        imagen_file = request.FILES.get('imagen')

        if not nombre or not precio:
            messages.error(request, 'El nombre y el precio son requeridos.')
            return render(request, 'platos/form.html', {'plato': plato, 'titulo': f'Editar {plato.nombre}'})

        plato.nombre = nombre
        plato.precio = precio
        plato.activo = activo

        if imagen_file:
            try:
                plato.imagen_base64 = process_image_to_base64(imagen_file)
            except Exception as e:
                messages.error(request, f'Error al procesar la imagen: {e}')
                return render(request, 'platos/form.html', {'plato': plato, 'titulo': f'Editar {plato.nombre}'})

        plato.save()
        messages.success(request, f'¡Plato "{plato.nombre}" actualizado exitosamente!')
        return redirect('platos_list')

    return render(request, 'platos/form.html', {'plato': plato, 'titulo': f'Editar {plato.nombre}'})

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
    except Exception:
        # Si tiene órdenes asociadas
        plato.activo = False
        plato.save()
        messages.warning(request, f'El plato "{nombre}" tiene historial de ventas, por lo que fue desactivado en lugar de eliminado.')
    return redirect('platos_list')


