from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('', views.reportes_view, name='reportes'),
    path('reportes/', views.reportes_view, name='reportes_alias'),
    path('pos/', views.pos_view, name='pos'),
    path('pos/cobrar/<int:orden_id>/', views.cobrar_orden, name='cobrar_orden'),
    path('cocina/', views.cocina_view, name='cocina'),
    path('cocina/estado/<int:orden_id>/<str:nuevo_estado>/', views.cambiar_estado_orden, name='cambiar_estado'),
    path('api/cocina-ordenes/', views.api_cocina_ordenes, name='api_cocina_ordenes'),
    
    # CRUD Platos (Superusuario)
    path('platos/', views.platos_list_view, name='platos_list'),
    path('platos/nuevo/', views.plato_create_view, name='plato_create'),
    path('platos/editar/<int:plato_id>/', views.plato_edit_view, name='plato_edit'),
    path('platos/toggle/<int:plato_id>/', views.plato_toggle_status_view, name='plato_toggle_status'),
    path('platos/eliminar/<int:plato_id>/', views.plato_delete_view, name='plato_delete'),

    # CRUD Categorías (Superusuario)
    path('categorias/', views.categorias_list_view, name='categorias_list'),
    path('categorias/nueva/', views.categoria_create_view, name='categoria_create'),
    path('categorias/editar/<int:categoria_id>/', views.categoria_edit_view, name='categoria_edit'),
    path('categorias/eliminar/<int:categoria_id>/', views.categoria_delete_view, name='categoria_delete'),
]


