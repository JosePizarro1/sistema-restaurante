from django.urls import path
from django.contrib.auth.views import LogoutView
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
]
