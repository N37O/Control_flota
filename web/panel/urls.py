from django.urls import path
from . import views

app_name = 'panel'

urlpatterns = [
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('usuarios/', views.usuarios_view, name='usuarios'),
    path('roles/', views.roles_view, name='roles'),
    # Nuevas rutas de Catálogos (Semana 3)
    path('catalogos/unidades/', views.unidades_view, name='unidades'),
    path('catalogos/conductores/', views.conductores_view, name='conductores'),
    # Nuevas rutas de la Semana 4
    path('clientes/', views.clientes_view, name='clientes'),
    path('viajes/', views.viajes_view, name='viajes'),
    path('cargas/', views.cargas_view, name='cargas'),
    path('tipos-carga/', views.tipos_carga_view, name='tipos_carga'),
    path('asignar-conductor/', views.asignar_conductor_view, name='asignar_conductor'),
    path('desasignar-conductor/', views.desasignar_conductor_view, name='desasignar_conductor'),
    path('quitar-conductor/', views.quitar_conductor_view, name='quitar_conductor'),
    path('control/', views.control_view, name='control'),
    path('seguimiento-gps/', views.seguimiento_gps_view, name='seguimiento_gps'),
    path('reportes/', views.reportes_view, name='reportes'),
]