from django.db import models

class Plato(models.Model):
    nombre = models.CharField(max_length=100)
    precio = models.DecimalField(max_digits=8, decimal_places=2)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} - S/. {self.precio}"

class Orden(models.Model):
    METODOS_PAGO = [
        ('PENDIENTE', 'Pendiente de Pago'),
        ('EFECTIVO', 'Efectivo'),
        ('YAPE', 'Yape / Plin'),
        ('TRANSFERENCIA', 'Transferencia'),
    ]

    ESTADOS_ORDEN = [
        ('PENDIENTE', 'En Cocina'),
        ('LISTO', 'Plato Listo (Pendiente Cobro)'),
        ('PAGADO', 'Pagado / Cerrado'),
        ('CANCELADO', 'Cancelado'),
    ]

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO, default='PENDIENTE')
    estado = models.CharField(max_length=20, choices=ESTADOS_ORDEN, default='PENDIENTE')
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"Orden #{self.id} - {self.estado} ({self.get_metodo_pago_display()})"

class DetalleOrden(models.Model):
    orden = models.ForeignKey(Orden, related_name='detalles', on_delete=models.CASCADE)
    plato = models.ForeignKey(Plato, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=8, decimal_places=2)

    def subtotal(self):
        return self.cantidad * self.precio_unitario
