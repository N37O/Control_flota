import requests
from django.conf import settings
from django.contrib import messages


class APIClient:
    """Cliente para consumir la API REST de Django"""
    
    def __init__(
        self,
        token=None,
        refresh_token=None,
        on_token_refresh=None,
    ):
        self.base_url = settings.API_BASE_URL.rstrip('/')
        self.token = token
        self.refresh_token = refresh_token
        self.on_token_refresh = on_token_refresh
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
        })
        if token:
            self.session.headers.update({
                'Authorization': f'Bearer {token}'
            })
        self.session.hooks['response'].append(self._refresh_on_unauthorized)

    @classmethod
    def from_request(cls, request):
        """Create an API client that can refresh and persist this session's tokens."""
        def update_tokens(access_token, refresh_token):
            request.session['access_token'] = access_token
            request.session['refresh_token'] = refresh_token

        return cls(
            token=request.session.get('access_token'),
            refresh_token=request.session.get('refresh_token'),
            on_token_refresh=update_tokens,
        )

    def _refresh_on_unauthorized(self, response, **kwargs):
        if (
            response.status_code != 401
            or not self.refresh_token
            or response.request.headers.get('X-Token-Retry') == '1'
        ):
            return response

        try:
            refresh_response = requests.post(
                f'{self.base_url}/usuarios/token/refresh/',
                json={'refresh': self.refresh_token},
                timeout=settings.API_TIMEOUT,
            )
            refresh_response.raise_for_status()
            tokens = refresh_response.json()
            access_token = tokens['access']
        except (requests.RequestException, ValueError, KeyError):
            return response

        self.token = access_token
        self.refresh_token = tokens.get('refresh', self.refresh_token)
        self.session.headers['Authorization'] = f'Bearer {access_token}'
        if self.on_token_refresh:
            self.on_token_refresh(access_token, self.refresh_token)

        response.close()
        retry_request = response.request.copy()
        retry_request.headers['Authorization'] = f'Bearer {access_token}'
        retry_request.headers['X-Token-Retry'] = '1'
        return self.session.send(
            retry_request,
            timeout=settings.API_TIMEOUT,
        )
    
    def _handle_response(self, response):
        """Maneja la respuesta de la API"""
        if response.status_code == 401:
            return None, 'Sesión expirada. Por favor, inicia sesión nuevamente.'
        elif response.status_code == 403:
            return None, 'No tienes permisos para realizar esta acción.'
        elif response.status_code >= 400:
            try:
                data = response.json()
            except ValueError:
                return None, f'Error {response.status_code}'

            detail = data.get('detail') if isinstance(data, dict) else None
            if detail is not None:
                return None, self._format_api_error(detail)
            if isinstance(data, dict):
                errors = [
                    f'{field}: {self._format_api_error(value)}'
                    for field, value in data.items()
                ]
                if errors:
                    return None, '; '.join(errors)
            if isinstance(data, list):
                return None, self._format_api_error(data)
            return None, f'Error {response.status_code}'
        
        try:
            return response.json(), None
        except ValueError:
            return None, 'Error al procesar la respuesta'

    @classmethod
    def _format_api_error(cls, value):
        if isinstance(value, dict):
            return '; '.join(
                f'{field}: {cls._format_api_error(message)}'
                for field, message in value.items()
            )
        if isinstance(value, (list, tuple)):
            return '; '.join(cls._format_api_error(message) for message in value)
        return str(value)

    # ============ AUTENTICACIÓN ============
    
    def login(self, usuario, password):
        """Iniciar sesión en la API"""
        try:
            response = self.session.post(
                f'{self.base_url}/usuarios/login/',
                json={'usuario': usuario, 'password': password},
                timeout=settings.API_TIMEOUT
            )
            if response.status_code == 401:
                try:
                    data = response.json()
                except ValueError:
                    return None, 'Usuario o contraseña incorrectos.'
                if isinstance(data, dict) and data.get('error'):
                    return None, self._format_api_error(data['error'])
                return None, 'Usuario o contraseña incorrectos.'

            data, error = self._handle_response(response)
            return data, error
        except requests.exceptions.ConnectionError:
            return None, 'No se pudo conectar con el servidor API'
        except requests.exceptions.Timeout:
            return None, 'La petición tardó demasiado tiempo'
    
    # ============ USUARIOS ============
    
    def get_usuarios(self):
        """Obtener lista de usuarios"""
        response = self.session.get(f'{self.base_url}/usuarios/usuarios/')
        return self._handle_response(response)
    
    def create_usuario(self, data):
        """Crear nuevo usuario"""
        response = self.session.post(
            f'{self.base_url}/usuarios/usuarios/',
            json=data
        )
        return self._handle_response(response)
    
    def update_usuario(self, id_usuario, data):
        """Actualizar usuario"""
        response = self.session.put(
            f'{self.base_url}/usuarios/usuarios/{id_usuario}/',
            json=data
        )
        return self._handle_response(response)
    
    def delete_usuario(self, id_usuario):
        """Eliminar usuario"""
        response = self.session.delete(
            f'{self.base_url}/usuarios/usuarios/{id_usuario}/'
        )
        return self._handle_response(response)

       
    def toggle_usuario_activo(self, id_usuario, activo):
        """Activar o desactivar usuario"""
        response = self.session.patch(
            f'{self.base_url}/usuarios/usuarios/{id_usuario}/',
            json={'activo': activo}
        )
        return self._handle_response(response)

    
    def update_usuario(self, id_usuario, data):
        response = self.session.patch(f'{self.base_url}/usuarios/usuarios/{id_usuario}/', json=data)
        return self._handle_response(response)

    # ============ UNIDADES ============
    def update_unidad(self, id_unidad, data):
        """Actualizar unidad usando PATCH (actualización parcial)"""
        try:
            # Filtrar valores None para no enviarlos
            data_filtrado = {k: v for k, v in data.items() if v is not None}
            response = self.session.patch(
                f'{self.base_url}/unidades/unidades/{id_unidad}/',
                json=data_filtrado
            )
            return self._handle_response(response)
        except Exception as e:
            return None, f'Error de conexión: {str(e)}'

    def toggle_unidad_activo(self, id_unidad, activo):
        """Activar o desactivar unidad"""
        try:
            response = self.session.patch(
                f'{self.base_url}/unidades/unidades/{id_unidad}/',
                json={'activo': activo}
            )
            return self._handle_response(response)
        except Exception as e:
            return None, f'Error de conexión: {str(e)}'

    # ============ CONDUCTORES ============
    def update_conductor(self, id_conductor, data):
        response = self.session.patch(f'{self.base_url}/unidades/conductores/{id_conductor}/', json=data)
        return self._handle_response(response)

    def toggle_conductor_activo(self, id_conductor, activo):
        response = self.session.patch(f'{self.base_url}/unidades/conductores/{id_conductor}/', json={'activo': activo})
        return self._handle_response(response)
   
    def get_conductores(self):
        response = self.session.get(f'{self.base_url}/unidades/conductores/')
        return self._handle_response(response)

    def create_conductor(self, data):
        """Crear conductor sin imagen"""
        response = self.session.post(f'{self.base_url}/unidades/conductores/', json=data)
        return self._handle_response(response)

    def create_conductor_with_image(self, data, imagen):
        """Crear conductor con imagen de licencia"""
        files = {'licencia_imagen': (imagen.name, imagen, imagen.content_type or 'image/jpeg')}
        response = self.session.post(
            f'{self.base_url}/unidades/conductores/',
            data=data,
            files=files,
            timeout=getattr(settings, 'API_TIMEOUT', 20)
        )
        return self._handle_response(response)

    def update_conductor_with_image(self, id_conductor, data, imagen):
        """Actualizar conductor con nueva imagen de licencia"""
        files = {'licencia_imagen': (imagen.name, imagen, imagen.content_type or 'image/jpeg')}
        response = self.session.patch(
            f'{self.base_url}/unidades/conductores/{id_conductor}/',
            data=data,
            files=files,
            timeout=getattr(settings, 'API_TIMEOUT', 20)
        )
        return self._handle_response(response)

    def toggle_conductor_activo(self, id_conductor, activo):
        response = self.session.patch(f'{self.base_url}/unidades/conductores/{id_conductor}/', json={'activo': activo})
        return self._handle_response(response)

    # ============ CATÁLOGOS: UNIDADES ============
    def get_unidades(self):
        response = self.session.get(f'{self.base_url}/unidades/unidades/')
        return self._handle_response(response)

    def get_tipos_unidad(self):
        response = self.session.get(f'{self.base_url}/unidades/tipos/')
        return self._handle_response(response)

    def get_estados_unidad(self):
        response = self.session.get(f'{self.base_url}/unidades/estados/')
        return self._handle_response(response)

    def create_unidad(self, data):
        response = self.session.post(f'{self.base_url}/unidades/unidades/', json=data)
        return self._handle_response(response)
    
       # ============ ROLES ============
    
    def get_roles(self):
        """Obtener lista de roles"""
        try:
            response = self.session.get(f'{self.base_url}/usuarios/roles/')
            return self._handle_response(response)
        except Exception as e:
            return None, f'Error de conexión: {str(e)}'
    
    def create_rol(self, data):
        """Crear nuevo rol"""
        try:
            response = self.session.post(
                f'{self.base_url}/usuarios/roles/',
                json=data
            )
            return self._handle_response(response)
        except Exception as e:
            return None, f'Error de conexión al crear rol: {str(e)}'
    
    def delete_rol(self, id_rol):
        """Eliminar rol"""
        try:
            response = self.session.delete(
                f'{self.base_url}/usuarios/roles/{id_rol}/'
            )
            return self._handle_response(response)
        except Exception as e:
            return None, f'Error de conexión al eliminar rol: {str(e)}'
    
    # ============ UNIDADES (para semanas posteriores) ============
    
    def get_unidades(self):
        """Obtener lista de unidades"""
        response = self.session.get(f'{self.base_url}/unidades/unidades/')
        return self._handle_response(response)
    
    def get_unidades_disponibles(self):
        """Obtener unidades disponibles"""
        response = self.session.get(f'{self.base_url}/unidades/unidades/disponibles/')
        return self._handle_response(response)

    def quitar_conductor_unidad(self, id_unidad):
        """Llama a la acción directa de la API para quitar el conductor"""
        response = self.session.post(f'{self.base_url}/unidades/unidades/{id_unidad}/quitar-conductor/')
        return self._handle_response(response)
    
    # ============ CLIENTES ============

    def get_clientes(self):
        response = self.session.get(f'{self.base_url}/viajes/clientes/')
        return self._handle_response(response)

    def create_cliente(self, data):
        response = self.session.post(f'{self.base_url}/viajes/clientes/', json=data)
        return self._handle_response(response)

    def update_cliente(self, id_cliente, data):
        response = self.session.patch(f'{self.base_url}/viajes/clientes/{id_cliente}/', json=data)
        return self._handle_response(response)

    def toggle_cliente_activo(self, id_cliente, activo):
        response = self.session.patch(f'{self.base_url}/viajes/clientes/{id_cliente}/', json={'activo': activo})
        return self._handle_response(response)

    # ============ UBICACIONES ============

    def get_ubicaciones(self):
        response = self.session.get(f'{self.base_url}/viajes/ubicaciones/')
        return self._handle_response(response)

    def create_ubicacion(self, data):
        response = self.session.post(f'{self.base_url}/viajes/ubicaciones/', json=data)
        return self._handle_response(response)

    # ============ TIPOS DE CARGA ============

    def get_tipos_carga(self):
        response = self.session.get(f'{self.base_url}/viajes/tipos-carga/')
        return self._handle_response(response)

    def create_tipo_carga(self, data):
        response = self.session.post(f'{self.base_url}/viajes/tipos-carga/', json=data)
        return self._handle_response(response)

    def update_tipo_carga(self, id_tipo_carga, data):
        response = self.session.patch(
            f'{self.base_url}/viajes/tipos-carga/{id_tipo_carga}/',
            json=data
        )
        return self._handle_response(response)

    def delete_tipo_carga(self, id_tipo_carga):
        response = self.session.delete(
            f'{self.base_url}/viajes/tipos-carga/{id_tipo_carga}/'
        )
        return self._handle_response(response)

    # ============ VIAJES ============
    
    def get_viajes(self):
        """Obtener lista de viajes"""
        response = self.session.get(f'{self.base_url}/viajes/viajes/')
        return self._handle_response(response)

    def get_all_pages(self, endpoint):
        """Obtener todos los resultados de un endpoint paginado."""
        url = f'{self.base_url.rstrip("/")}/{endpoint.strip("/")}/'
        results = []
        page = 1

        while True:
            try:
                response = self.session.get(
                    url,
                    params={'page': page},
                    timeout=settings.API_TIMEOUT,
                )
            except requests.exceptions.RequestException as error:
                return None, f'Error de conexión al cargar {endpoint}: {error}'
            data, error = self._handle_response(response)
            if error:
                return None, error
            if not isinstance(data, dict) or not isinstance(data.get('results'), list):
                return None, f'La respuesta paginada de {endpoint} no tiene el formato esperado.'

            results.extend(data['results'])
            if not data.get('next'):
                return {'count': data.get('count', len(results)), 'results': results}, None
            page += 1

    def get_viaje(self, id_viaje):
        response = self.session.get(f'{self.base_url}/viajes/viajes/{id_viaje}/')
        return self._handle_response(response)

    def create_viaje(self, data):
        response = self.session.post(f'{self.base_url}/viajes/viajes/', json=data)
        return self._handle_response(response)

    def update_viaje(self, id_viaje, data):
        response = self.session.patch(f'{self.base_url}/viajes/viajes/{id_viaje}/', json=data)
        return self._handle_response(response)

    def delete_viaje(self, id_viaje):
        response = self.session.delete(f'{self.base_url}/viajes/viajes/{id_viaje}/')
        return self._handle_response(response)

    def cambiar_estado_viaje(self, id_viaje, estado):
        response = self.session.post(
            f'{self.base_url}/viajes/viajes/{id_viaje}/cambiar-estado/',
            json={'estado': estado}
        )
        return self._handle_response(response)
    
    def get_viajes_en_transito(self):
        """Obtener viajes en tránsito"""
        response = self.session.get(f'{self.base_url}/viajes/viajes/en_transito/')
        return self._handle_response(response)

    def get_posiciones_gps(self, id_viaje=None):
        params = {'id_viaje': id_viaje} if id_viaje else None
        response = self.session.get(
            f'{self.base_url}/viajes/posiciones-gps/',
            params=params,
        )
        return self._handle_response(response)

    def get_reporte_panel(self):
        response = self.session.get(f'{self.base_url}/reportes/panel/')
        return self._handle_response(response)

    def get_reporte_rendimiento(self):
        response = self.session.get(f'{self.base_url}/reportes/rendimiento/')
        return self._handle_response(response)

    def get_historial_viajes(self, filters=None):
        response = self.session.get(
            f'{self.base_url}/reportes/historial/',
            params=filters or {},
        )
        return self._handle_response(response)

    # ============ CARGAS ============

    def get_cargas(self, id_viaje=None):
        if id_viaje:
            response = self.session.get(f'{self.base_url}/viajes/cargas/?id_viaje={id_viaje}')
        else:
            response = self.session.get(f'{self.base_url}/viajes/cargas/')
        return self._handle_response(response)

    def create_carga(self, data):
        response = self.session.post(f'{self.base_url}/viajes/cargas/', json=data)
        return self._handle_response(response)

    def update_carga(self, id_carga, data):
        response = self.session.patch(f'{self.base_url}/viajes/cargas/{id_carga}/', json=data)
        return self._handle_response(response)

    def delete_carga(self, id_carga):
        response = self.session.delete(f'{self.base_url}/viajes/cargas/{id_carga}/')
        return self._handle_response(response)

    # ============ CONTROL ============

    def get_recargas(self):
        response = self.session.get(f'{self.base_url}/control/recargas/')
        return self._handle_response(response)

    def create_recarga(self, data):
        response = self.session.post(f'{self.base_url}/control/recargas/', json=data)
        return self._handle_response(response)

    def get_movimientos(self):
        response = self.session.get(f'{self.base_url}/control/movimientos/')
        return self._handle_response(response)

    def create_movimiento(self, data):
        response = self.session.post(f'{self.base_url}/control/movimientos/', json=data)
        return self._handle_response(response)
    
    # ============ REPORTES ============
    
    def get_panel_stats(self):
        """Obtener estadísticas del panel"""
        response = self.session.get(f'{self.base_url}/reportes/panel/')
        return self._handle_response(response)