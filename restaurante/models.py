from decimal import Decimal
from typing import ClassVar

from django.core.exceptions import ValidationError
from django.db import models


class Categoria(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)
    # Packability of a category (whether lines price a "para llevar" taper) is an
    # intrinsic property of the category — NOT derived from an active Menu row.
    # Defaults to False so a newly added category (admin-editable, no code) does
    # NOT silently incur a taper surcharge. The seed flags Entrada/Segundo
    # packable=True explicitly; Añadidos stays packable=False.
    packable = models.BooleanField(default=False)

    class Meta:
        ordering = ('orden', 'nombre')
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'

    def __str__(self):
        return self.nombre


class Plato(models.Model):
    categoria = models.ForeignKey(
        Categoria,
        related_name='platos',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    nombre = models.CharField(max_length=100)
    precio = models.DecimalField(max_digits=8, decimal_places=2)
    activo = models.BooleanField(default=True)
    imagen_base64 = models.TextField(blank=True, null=True)
    imagen_alt = models.CharField(max_length=100, blank=True, default='')

    def __str__(self):
        return f"{self.nombre} - S/. {self.precio}"


class Menu(models.Model):
    nombre = models.CharField(max_length=50, default="Menú")
    precio = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("13.00"))
    categoria_entrada = models.ForeignKey(
        Categoria,
        related_name='menus_entrada',
        on_delete=models.PROTECT,
    )
    categoria_segundo = models.ForeignKey(
        Categoria,
        related_name='menus_segundo',
        on_delete=models.PROTECT,
    )
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Menú'
        verbose_name_plural = 'Menús'

    def __str__(self):
        return f"{self.nombre} - S/. {self.precio}"


class Configuracion(models.Model):
    recargo_por_taper = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("1.00"))

    class Meta:
        verbose_name = 'Configuración'
        verbose_name_plural = 'Configuración'

    def __str__(self):
        return f"Configuración (recargo por taper: S/. {self.recargo_por_taper})"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


class Orden(models.Model):
    METODOS_PAGO = (
        ('PENDIENTE', 'Pendiente de Pago'),
        ('EFECTIVO', 'Efectivo'),
        ('YAPE', 'Yape / Plin'),
        ('TRANSFERENCIA', 'Transferencia'),
    )

    ESTADOS_ORDEN = (
        ('PENDIENTE', 'En Cocina'),
        ('LISTO', 'Plato Listo (Pendiente Cobro)'),
        ('PAGADO', 'Pagado / Cerrado'),
        ('CANCELADO', 'Cancelado'),
    )

    TIPOS_SERVICIO = (
        ('MESA', 'En Mesa'),
        ('LLEVAR', 'Para Llevar'),
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO, default='PENDIENTE')
    estado = models.CharField(max_length=20, choices=ESTADOS_ORDEN, default='PENDIENTE')
    tipo_servicio = models.CharField(max_length=20, choices=TIPOS_SERVICIO, default='MESA')
    nota_general = models.CharField(max_length=255, blank=True, default='')
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        ordering = ('-fecha_creacion',)

    def __str__(self):
        return f"Orden #{self.id} - {self.estado} ({self.get_metodo_pago_display()})"

    @property
    def total_tapers(self):
        return sum(d.taper_count() for d in self.detalles.all())

    @property
    def subtotal_consumo(self):
        return sum(d.subtotal() for d in self.detalles.all())

    @property
    def monto_tapers(self):
        tapers = self.total_tapers
        if tapers > 0:
            return tapers * Configuracion.get().recargo_por_taper
        return Decimal("0.00")

    def computar_total(self):
        total = self.subtotal_consumo
        tapers = self.total_tapers
        if tapers > 0:
            total += tapers * Configuracion.get().recargo_por_taper
        return total


class DetalleOrden(models.Model):
    orden = models.ForeignKey(Orden, related_name='detalles', on_delete=models.CASCADE)
    plato = models.ForeignKey(Plato, on_delete=models.PROTECT, null=True, blank=True)
    menu = models.ForeignKey(Menu, on_delete=models.PROTECT, null=True, blank=True)
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=8, decimal_places=2)
    nota = models.CharField(max_length=255, blank=True, default='')
    es_para_llevar = models.BooleanField(default=False)
    entrada_para_llevar = models.BooleanField(default=False)
    segundo_para_llevar = models.BooleanField(default=False)

    class Meta:
        # Exactly one of plato/menu must be set. clean() enforces this at the
        # form/model layer, but objects.create() bypasses it; this DB constraint
        # guarantees no orphan line (neither) or composite+single line (both)
        # can persist.
        constraints: ClassVar[list[models.CheckConstraint]] = [
            models.CheckConstraint(
                name="detalle_orden_exactly_one_plato_or_menu",
                condition=(
                    models.Q(plato__isnull=False) & models.Q(menu__isnull=True)
                )
                | (models.Q(plato__isnull=True) & models.Q(menu__isnull=False)),
            ),
        ]

    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def taper_count(self):
        is_llevar = self.es_para_llevar or (self.orden_id and self.orden.tipo_servicio == 'LLEVAR')
        if self.menu_id is not None:
            count = 0
            if self.entrada_para_llevar:
                count += 1
            if self.segundo_para_llevar:
                count += 1
            if count == 0 and is_llevar:
                count = 2
            return count * self.cantidad
        if (
            self.plato_id is not None
            and is_llevar
            and self.plato.categoria_id is not None
            and self.plato.categoria.packable
        ):
            return self.cantidad
        return 0
        return 0

    def clean(self):
        # Exactly one of plato/menu must be set: no orphan lines (neither) and
        # no line pricing a composite menu AND a single plato (both).
        super().clean()
        if (self.plato_id is None) == (self.menu_id is None):
            raise ValidationError(
                "Cada línea de orden debe referenciar exactamente un plato o un menú."
            )
