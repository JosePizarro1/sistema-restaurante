from django.contrib import admin
from .models import Plato, Orden, DetalleOrden

@admin.register(Plato)
class PlatoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'precio', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre',)

class DetalleOrdenInline(admin.TabularInline):
    model = DetalleOrden
    extra = 0

@admin.register(Orden)
class OrdenAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha_creacion', 'metodo_pago', 'estado', 'total')
    list_filter = ('metodo_pago', 'estado', 'fecha_creacion')
    inlines = [DetalleOrdenInline]
