from django.shortcuts import redirect
from django.urls import reverse


class JWTAuthMiddleware:
    """
    Middleware que verifica la autenticación JWT en cada petición.
    Si el usuario no está autenticado, lo redirige al login.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # URLs que no requieren autenticación
        public_urls = [
            reverse('panel:login'),
            reverse('panel:logout'),
        ]
        
        # Si la URL es pública, continuar normalmente
        if request.path in public_urls:
            return self.get_response(request)
        
        # Verificar si hay token en la sesión
        if not request.session.get('access_token'):
            return redirect('panel:login')
        
        # Verificar si hay usuario en la sesión
        if not request.session.get('user_data'):
            return redirect('panel:login')
        
        # Agregar datos del usuario al request para usarlos en templates
        request.user_data = request.session.get('user_data')
        request.access_token = request.session.get('access_token')
        
        return self.get_response(request)