from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'roles', views.RolViewSet)
router.register(r'usuarios', views.UsuarioViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('login/', views.login_view, name='login'),
]