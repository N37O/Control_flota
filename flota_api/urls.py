from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

# Vista simple para la raíz
def inicio_api(request):
    return JsonResponse({
        "mensaje": "Bienvenido a la API del Sistema de Gestión de Flotas",
        "version": "1.0"
    })

urlpatterns = [
    path('', inicio_api),  # <-- Esta línea atenderá la ruta http://127.0.0.1:8000/
    path('admin/', admin.site.urls),
    path('api/usuarios/', include('usuarios.urls')),
    path('api/unidades/', include('unidades.urls')),
    path('api/viajes/', include('viajes.urls')),
    path('api/reportes/', include('reportes.urls')),
]