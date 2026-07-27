from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone
from .models import Plato, Orden, DetalleOrden
import json

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

        # Se envía a cocina sin método de pago aún
        orden = Orden.objects.create(metodo_pago='PENDIENTE', estado='PENDIENTE')
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
                precio_unitario=plato.precio
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

@login_required
def reportes_view(request):
    hoy = timezone.now().date()
    ordenes_hoy = Orden.objects.filter(fecha_creacion__date=hoy, estado='PAGADO')
    
    total_ventas = ordenes_hoy.aggregate(Sum('total'))['total__sum'] or 0
    ventas_efectivo = ordenes_hoy.filter(metodo_pago='EFECTIVO').aggregate(Sum('total'))['total__sum'] or 0
    ventas_yape = ordenes_hoy.filter(metodo_pago='YAPE').aggregate(Sum('total'))['total__sum'] or 0
    ventas_transferencia = ordenes_hoy.filter(metodo_pago='TRANSFERENCIA').aggregate(Sum('total'))['total__sum'] or 0

    platos_mas_vendidos = DetalleOrden.objects.filter(orden__fecha_creacion__date=hoy, orden__estado='PAGADO') \
        .values('plato__nombre') \
        .annotate(total_cantidad=Sum('cantidad')) \
        .order_by('-total_cantidad')[:5]

    context = {
        'fecha': hoy,
        'total_ventas': total_ventas,
        'ventas_efectivo': ventas_efectivo,
        'ventas_yape': ventas_yape,
        'ventas_transferencia': ventas_transferencia,
        'platos_mas_vendidos': platos_mas_vendidos,
    }
    return render(request, 'reportes.html', context)
