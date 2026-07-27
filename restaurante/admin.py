import io
import base64
from django import forms
from django.contrib import admin
from django.utils.html import format_html
from PIL import Image
from .models import Plato, Orden, DetalleOrden


class PlatoForm(forms.ModelForm):
    imagen_upload = forms.ImageField(required=False, label='Imagen del Plato')

    class Meta:
        model = Plato
        fields = ['nombre', 'precio', 'activo', 'imagen_alt']

    def save(self, commit=True):
        instance = super().save(commit=False)
        imagen_file = self.cleaned_data.get('imagen_upload')

        if imagen_file:
            img = Image.open(imagen_file)
            # Convertir a RGB si es RGBA (PNG con transparencia)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            # Redimensionar a máximo 400x300 manteniendo proporción
            img.thumbnail((400, 300), Image.LANCZOS)
            # Comprimir a JPEG calidad 70
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=70, optimize=True)
            buffer.seek(0)
            encoded = base64.b64encode(buffer.read()).decode('utf-8')
            instance.imagen_base64 = f"data:image/jpeg;base64,{encoded}"

        if commit:
            instance.save()
        return instance


@admin.register(Plato)
class PlatoAdmin(admin.ModelAdmin):
    form = PlatoForm
    list_display = ('nombre', 'precio', 'activo', 'preview_imagen')
    list_filter = ('activo',)
    search_fields = ('nombre',)
    fields = ('nombre', 'precio', 'activo', 'imagen_upload', 'imagen_alt', 'preview_admin')
    readonly_fields = ('preview_admin',)

    def preview_imagen(self, obj):
        if obj.imagen_base64:
            return format_html('<img src="{}" style="height:40px;border-radius:6px;">', obj.imagen_base64)
        return '—'
    preview_imagen.short_description = 'Vista previa'

    def preview_admin(self, obj):
        if obj.imagen_base64:
            return format_html(
                '<img src="{}" style="max-width:300px;max-height:200px;border-radius:10px;border:1px solid #eee;">',
                obj.imagen_base64
            )
        return 'No hay imagen cargada.'
    preview_admin.short_description = 'Imagen actual'


class DetalleOrdenInline(admin.TabularInline):
    model = DetalleOrden
    extra = 0
    readonly_fields = ('plato', 'cantidad', 'precio_unitario', 'nota')


@admin.register(Orden)
class OrdenAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha_creacion', 'metodo_pago', 'estado', 'total')
    list_filter = ('metodo_pago', 'estado', 'fecha_creacion')
    inlines = [DetalleOrdenInline]
