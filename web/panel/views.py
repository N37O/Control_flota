from decimal import Decimal, InvalidOperation
from datetime import timedelta
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .services import APIClient


def login_view(request):
    """Vista de inicio de sesión"""
    if request.session.get('access_token'):
        return redirect('panel:dashboard')
    
    if request.method == 'POST':
        usuario = request.POST.get('usuario', '').strip()
        password = request.POST.get('password', '').strip()
        
        if not usuario or not password:
            messages.error(request, 'Por favor, completa todos los campos')
            return render(request, 'panel/login.html')
        
        client = APIClient()
        data, error = client.login(usuario, password)
        
        if error:
            messages.error(request, error)
            return render(request, 'panel/login.html')
        
        request.session['access_token'] = data['access']
        request.session['refresh_token'] = data['refresh']
        request.session['user_data'] = data['usuario']
        
        messages.success(request, f'Bienvenido, {data["usuario"]["nombre"]}!')
        return redirect('panel:dashboard')
    
    return render(request, 'panel/login.html')


def logout_view(request):
    """Cerrar sesión"""
    request.session.flush()
    messages.success(request, 'Sesión cerrada correctamente')
    return redirect('panel:login')


def quitar_conductor_view(request):
    """Vista directa para quitar conductor de una unidad"""
    token = request.session.get('access_token')
    client = APIClient.from_request(request)
    user_data = request.user_data

    if request.method == 'POST' and user_data.get('rol_nombre') == 'ADMINISTRADOR':
        id_unidad = request.POST.get('id_unidad')

        res, err = client.quitar_conductor_unidad(id_unidad)

        if res:
            messages.success(request, '✅ Conductor quitado de la unidad exitosamente.')
        else:
            messages.error(request, f'Error: {err}')

    return redirect('panel:unidades')


def asignar_conductor_view(request):
    """Vista específica para asignar/desasignar conductor a unidad"""
    token = request.session.get('access_token')
    client = APIClient.from_request(request)
    user_data = request.user_data
    is_admin = user_data.get('rol_nombre') == 'ADMINISTRADOR'

    if not is_admin:
        messages.error(request, 'No tienes permisos para realizar esta acción.')
        return redirect('panel:unidades')

    if request.method == 'POST':
        action = request.POST.get('action')
        id_unidad = request.POST.get('id_unidad')

        if action == 'asignar':
            id_conductor = request.POST.get('id_conductor')

            if not id_conductor or id_conductor == '':
                messages.error(request, '⚠️ Debes seleccionar un conductor.')
                return redirect('panel:unidades')

            # Validar que el conductor no esté asignado a otra unidad.
            todas_unidades, _ = client.get_unidades()
            for u in (todas_unidades.get('results', []) if todas_unidades else []):
                if str(u.get('id_conductor')) == str(id_conductor):
                    messages.error(request, f'⚠️ Este conductor ya está asignado a la unidad {u.get("placa")}.' )
                    return redirect('panel:unidades')

            data = {'id_conductor': int(id_conductor)}
            res, err = client.update_unidad(id_unidad, data)

            if res:
                messages.success(request, '✅ Conductor asignado exitosamente.')
            else:
                messages.error(request, f'Error: {err}')

        elif action == 'desasignar':
            data = {'id_conductor': None}
            res, err = client.update_unidad(id_unidad, data)

            if res:
                messages.success(request, '✅ Conductor desasignado exitosamente.')
            else:
                messages.error(request, f'Error: {err}')

    return redirect('panel:unidades')


def desasignar_conductor_view(request):
    """Vista simple para desasignar conductor de una unidad"""
    token = request.session.get('access_token')
    client = APIClient.from_request(request)
    user_data = request.user_data
    is_admin = user_data.get('rol_nombre') == 'ADMINISTRADOR'

    if not is_admin:
        messages.error(request, 'No tienes permisos.')
        return redirect('panel:unidades')

    if request.method == 'POST':
        id_unidad = request.POST.get('id_unidad')

        # Enviar explícitamente el valor None de Python (no el string 'null').
        res, err = client.update_unidad(id_unidad, {'id_conductor': None})

        if res:
            messages.success(request, '✅ Conductor desasignado exitosamente.')
        else:
            messages.error(request, f'Error: {err}')

    return redirect('panel:unidades')


def dashboard_view(request):
    """Presenta un resumen operativo de la flota y sus viajes."""
    token = request.session.get('access_token')
    client = APIClient.from_request(request)
    context = {
        'user_data': request.user_data,
        'dashboard_error': None,
        'total_unidades': 0,
        'unidades_disponibles': 0,
        'unidades_en_viaje': 0,
        'unidades_mantenimiento': 0,
        'unidades_otros_estados': 0,
        'unidades_combustible_bajo': 0,
        'unidades_sin_lectura': 0,
        'viajes_programados': 0,
        'viajes_en_curso': 0,
        'viajes_completados': 0,
        'viajes_cancelados': 0,
        'total_viajes': 0,
        'unidades_disponibles_pct': 0,
        'unidades_en_viaje_pct': 0,
        'unidades_mantenimiento_pct': 0,
        'viajes_programados_pct': 0,
        'viajes_en_curso_pct': 0,
        'viajes_completados_pct': 0,
        'viajes_cancelados_pct': 0,
        'viajes_ultimos_30_dias': 0,
        'km_ultimos_30_dias': Decimal('0'),
        'rendimiento_ultimos_30_dias': None,
        'viajes_recientes': [],
        'viajes_con_alerta': [],
    }

    unidades_data, unidades_error = client.get_all_pages('unidades/unidades')
    viajes_data, viajes_error = client.get_all_pages('viajes/viajes')
    errores = [error for error in (unidades_error, viajes_error) if error]
    if errores:
        context['dashboard_error'] = 'No se pudieron cargar todas las estadísticas: ' + ' '.join(errores)

    unidades = unidades_data.get('results', []) if unidades_data else []
    viajes = viajes_data.get('results', []) if viajes_data else []

    def entero(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def decimal(value):
        if value in (None, ''):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None

    def fecha_local(value):
        if not value:
            return None
        fecha = parse_datetime(str(value))
        if fecha is None:
            return None
        if timezone.is_naive(fecha):
            fecha = timezone.make_aware(fecha, timezone.get_current_timezone())
        return timezone.localtime(fecha)

    activos = [unidad for unidad in unidades if unidad.get('activo', True)]
    context['total_unidades'] = len(activos)
    for unidad in activos:
        estado = (unidad.get('estado_nombre') or '').strip().upper().replace(' ', '_')
        if estado == 'DISPONIBLE':
            context['unidades_disponibles'] += 1
        elif estado in ('EN_VIAJE', 'EN_TRANSITO'):
            context['unidades_en_viaje'] += 1
        elif estado in ('MANTENIMIENTO', 'EN_MANTENIMIENTO'):
            context['unidades_mantenimiento'] += 1

        lectura = decimal(
            unidad.get('combustible_actual_gal')
            if unidad.get('combustible_actual_gal') is not None
            else unidad.get('ultima_lectura_combustible_gal')
        )
        capacidad = decimal(unidad.get('capacidad_tanque_gal'))
        if lectura is None:
            context['unidades_sin_lectura'] += 1
        elif capacidad and capacidad > 0 and lectura <= capacidad * Decimal('0.25'):
            context['unidades_combustible_bajo'] += 1

    estados_viaje = {
        1: 'viajes_programados',
        2: 'viajes_en_curso',
        3: 'viajes_completados',
        4: 'viajes_cancelados',
    }
    for viaje in viajes:
        estado = entero(viaje.get('id_estado_viaje'))
        viaje['estado_dashboard'] = estado
        fecha = fecha_local(
            viaje.get('fecha_llegada_real')
            or viaje.get('fecha_salida')
            or viaje.get('fecha_programada')
        )
        viaje['fecha_dashboard'] = (
            fecha.strftime('%d/%m/%Y %H:%M') if fecha else 'Sin fecha'
        )
        viaje['_fecha_dashboard_timestamp'] = fecha.timestamp() if fecha else 0
        clave = estados_viaje.get(estado)
        if clave:
            context[clave] += 1

    context['unidades_otros_estados'] = max(
        0,
        context['total_unidades']
        - context['unidades_disponibles']
        - context['unidades_en_viaje']
        - context['unidades_mantenimiento'],
    )
    for clave in ('disponibles', 'en_viaje', 'mantenimiento', 'otros_estados'):
        total = context['total_unidades']
        context[f'unidades_{clave}_pct'] = round(
            context[f'unidades_{clave}'] * 100 / total
        ) if total else 0
    total_viajes = len(viajes)
    context['total_viajes'] = total_viajes
    for clave in ('programados', 'en_curso', 'completados', 'cancelados'):
        context[f'viajes_{clave}_pct'] = round(
            context[f'viajes_{clave}'] * 100 / total_viajes
        ) if total_viajes else 0

    ahora_local = timezone.localtime()
    inicio_periodo = ahora_local - timedelta(days=30)
    km_periodo = Decimal('0')
    km_rendimiento_periodo = Decimal('0')
    galones_periodo = Decimal('0')
    viajes_completados_periodo = []
    for viaje in viajes:
        if entero(viaje.get('id_estado_viaje')) != 3:
            continue
        fecha = fecha_local(viaje.get('fecha_llegada_real') or viaje.get('fecha_salida'))
        if fecha is None or fecha < inicio_periodo:
            continue
        viajes_completados_periodo.append(viaje)
        km = decimal(viaje.get('km_recorridos'))
        galones = decimal(viaje.get('galones_consumidos'))
        if km is not None and km > 0:
            km_periodo += km
        if km is not None and km > 0 and galones is not None and galones > 0:
            km_rendimiento_periodo += km
            galones_periodo += galones

    context['viajes_ultimos_30_dias'] = len(viajes_completados_periodo)
    context['km_ultimos_30_dias'] = km_periodo
    if galones_periodo > 0:
        context['rendimiento_ultimos_30_dias'] = (
            km_rendimiento_periodo / galones_periodo
        ).quantize(Decimal('0.01'))

    viajes_ordenados = sorted(
        viajes,
        key=lambda viaje: viaje['_fecha_dashboard_timestamp'],
        reverse=True,
    )
    context['viajes_recientes'] = viajes_ordenados[:6]
    context['viajes_con_alerta'] = [
        viaje for viaje in viajes_ordenados
        if str(viaje.get('alerta_consumo', '')).strip().lower() in ('true', '1')
    ][:5]

    return render(request, 'panel/dashboard.html', context)


def usuarios_view(request):
    """Vista de gestión de usuarios con CRUD completo"""
    token = request.session.get('access_token')
    client = APIClient.from_request(request)
    user_data = request.user_data
    is_admin = user_data.get('rol_nombre') == 'ADMINISTRADOR'
    user_id_actual = user_data.get('id_usuario')
    
    context = {'user_data': user_data, 'is_admin': is_admin}
    
    # Obtener todos los usuarios (activos e inactivos)
    usuarios, _ = client.get_usuarios()
    context['usuarios'] = usuarios.get('results', []) if usuarios else []
    
    roles, _ = client.get_roles()
    context['roles'] = roles.get('results', []) if roles else []

    if request.method == 'POST' and is_admin:
        action = request.POST.get('action')
        id_target = request.POST.get('id_usuario')
        
        # Validación: No permitir modificar la propia cuenta
        if str(id_target) == str(user_id_actual) and action in ['toggle_activo', 'delete']:
            messages.error(request, ' No puedes modificar tu propia cuenta.')
            return redirect('panel:usuarios')

        if action == 'create':
            data = {
                'id_rol': int(request.POST.get('id_rol')),
                'nombre': request.POST.get('nombre'),
                'correo': request.POST.get('correo'),
                'usuario': request.POST.get('usuario'),
                'password': request.POST.get('password'),
                'activo': True
            }
            res, err = client.create_usuario(data)
            if res:
                messages.success(request, ' Usuario creado exitosamente.')
            else:
                messages.error(request, err or 'Error al crear usuario.')
                
        elif action == 'update':
            data = {
                'id_rol': int(request.POST.get('id_rol')),
                'nombre': request.POST.get('nombre'),
                'correo': request.POST.get('correo'),
                'usuario': request.POST.get('usuario'),
                'activo': True
            }
            # Solo actualizar contraseña si se proporcionó una nueva
            if request.POST.get('password'):
                data['password'] = request.POST.get('password')
            
            res, err = client.update_usuario(id_target, data)
            if res:
                messages.success(request, ' Usuario actualizado exitosamente.')
            else:
                messages.error(request, err or 'Error al actualizar usuario.')
                
        elif action == 'toggle_activo':
            nuevo_estado = request.POST.get('nuevo_estado') == 'true'
            
            # Validación: No desactivar al último administrador
            if not nuevo_estado:
                admins_activos = [u for u in context['usuarios'] 
                                  if u.get('rol_nombre') == 'ADMINISTRADOR' and u.get('activo')]
                target_user = next((u for u in context['usuarios'] 
                                   if str(u.get('id_usuario')) == str(id_target)), None)
                
                if target_user and target_user.get('rol_nombre') == 'ADMINISTRADOR' and len(admins_activos) <= 1:
                    messages.error(request, ' No se puede desactivar al último administrador del sistema.')
                    return redirect('panel:usuarios')
            
            res, err = client.toggle_usuario_activo(id_target, nuevo_estado)
            if res:
                estado_texto = "activado" if nuevo_estado else "desactivado"
                messages.success(request, f' Usuario {estado_texto} exitosamente.')
            else:
                messages.error(request, err or 'Error al cambiar estado.')
                
        elif action == 'delete':
            # Validación: No eliminar al último administrador
            admins_activos = [u for u in context['usuarios'] 
                              if u.get('rol_nombre') == 'ADMINISTRADOR']
            target_user = next((u for u in context['usuarios'] 
                               if str(u.get('id_usuario')) == str(id_target)), None)
            
            if target_user and target_user.get('rol_nombre') == 'ADMINISTRADOR' and len(admins_activos) <= 1:
                messages.error(request, ' No se puede eliminar al último administrador del sistema.')
                return redirect('panel:usuarios')
            
            res, err = client.delete_usuario(id_target)
            if res:
                messages.success(request, ' Usuario eliminado exitosamente.')
            else:
                messages.error(request, err or 'Error al eliminar usuario.')
        
        return redirect('panel:usuarios')
    
    return render(request, 'panel/usuarios.html', context)


def roles_view(request):
    """Vista de gestión de roles con CRUD"""
    token = request.session.get('access_token')
    client = APIClient.from_request(request)
    user_data = request.user_data
    is_admin = user_data.get('rol_nombre') == 'ADMINISTRADOR'
    
    context = {'user_data': user_data, 'is_admin': is_admin}
    
    try:
        roles, error = client.get_roles()
        if roles:
            context['roles'] = roles.get('results', [])
        else:
            messages.error(request, error or 'Error al cargar la lista de roles')
            context['roles'] = []
    except Exception as e:
        messages.error(request, f'Error inesperado al cargar roles: {str(e)}')
        context['roles'] = []
    
    if request.method == 'POST' and is_admin:
        action = request.POST.get('action')
        
        if action == 'create':
            data = {
                'nombre': request.POST.get('nombre', '').strip().upper(),
                'descripcion': request.POST.get('descripcion', '').strip(),
            }
            
            if not data['nombre']:
                messages.error(request, 'El nombre del rol es obligatorio.')
            else:
                try:
                    res, err = client.create_rol(data)
                    if res:
                        messages.success(request, f'Rol "{data["nombre"]}" creado exitosamente.')
                    else:
                        messages.error(request, err or 'Error al crear el rol. ¿Ya existe un rol con ese nombre?')
                except Exception as e:
                    messages.error(request, f'Error de conexión con la API: {str(e)}')
            
            return redirect('panel:roles')
            
        elif action == 'delete':
            id_rol = request.POST.get('id_rol')
            try:
                res, err = client.delete_rol(id_rol)
                if res:
                    messages.success(request, 'Rol eliminado exitosamente.')
                else:
                    messages.error(request, err or 'No se pudo eliminar el rol (¿tiene usuarios asignados?).')
            except Exception as e:
                messages.error(request, f'Error de conexión: {str(e)}')
            
            return redirect('panel:roles')
    
    return render(request, 'panel/roles.html', context)


def unidades_view(request):
    """Vista de unidades con asignación simplificada y desasignación correcta"""
    token = request.session.get('access_token')
    client = APIClient.from_request(request)
    user_data = request.user_data
    is_admin = user_data.get('rol_nombre') == 'ADMINISTRADOR'
    context = {'user_data': user_data, 'is_admin': is_admin}

    # Cargar datos para el formulario
    tipos, _ = client.get_tipos_unidad()
    context['tipos'] = tipos.get('results', []) if tipos else []
    
    estados, _ = client.get_estados_unidad()
    context['estados'] = estados.get('results', []) if estados else []
    
    # Cargar TODOS los conductores activos
    conductores_resp, _ = client.get_conductores()
    todos_conductores = conductores_resp.get('results', []) if conductores_resp else []
    context['todos_conductores'] = [c for c in todos_conductores if c.get('activo')]
    
    # Cargar TODAS las unidades
    unidades_resp, _ = client.get_unidades()
    todas_unidades = unidades_resp.get('results', []) if unidades_resp else []
    context['todas_unidades'] = todas_unidades
    
    # Identificar conductores ya asignados
    conductores_asignados = set()
    for u in todas_unidades:
        if u.get('id_conductor'):
            conductores_asignados.add(u['id_conductor'])
    
    # Conductores disponibles (no asignados)
    context['conductores_disponibles'] = [
        c for c in context['todos_conductores'] 
        if c.get('id_conductor') not in conductores_asignados
    ]
    
    # Mapeo de unidad -> conductor asignado
    context['unidad_conductor_map'] = {
        str(u['id_unidad']): u.get('id_conductor') 
        for u in todas_unidades
        if u.get('id_conductor')
    }

    if request.method == 'POST' and is_admin:
        action = request.POST.get('action')
        id_target = request.POST.get('id_unidad')
        
        # Función robusta para convertir a entero o None
        def safe_int_or_none(value):
            if value is None or str(value).strip() == '' or str(value).strip().lower() == 'none':
                return None
            try:
                return int(value)
            except (ValueError, TypeError):
                return None
        
        nuevo_conductor_id = safe_int_or_none(request.POST.get('id_conductor'))
        try:
            capacidad_ton = Decimal(request.POST.get('capacidad_ton', '').strip())
            capacidad_tanque_gal = Decimal(request.POST.get('capacidad_tanque_gal', '').strip())
        except (InvalidOperation, TypeError, AttributeError):
            messages.error(request, 'Indica capacidades válidas para la carga y el tanque.')
            return redirect('panel:unidades')

        if (
            not capacidad_ton.is_finite()
            or not capacidad_tanque_gal.is_finite()
            or capacidad_ton <= 0
            or capacidad_tanque_gal <= 0
        ):
            messages.error(request, 'Las capacidades de carga y del tanque deben ser mayores a cero.')
            return redirect('panel:unidades')

        data = {
            'placa': request.POST.get('placa', '').upper().strip(),
            'codigo_interno': request.POST.get('codigo_interno', '').strip(),
            'id_tipo_unidad': safe_int_or_none(request.POST.get('id_tipo_unidad')),
            'id_estado_unidad': safe_int_or_none(request.POST.get('id_estado_unidad')),
            'capacidad_ton': float(capacidad_ton),
            'capacidad_tanque_gal': float(capacidad_tanque_gal),
            'id_conductor': nuevo_conductor_id,  # ✅ Se envía explícitamente (puede ser None)
        }
        
        if action == 'create':
            if nuevo_conductor_id and nuevo_conductor_id in conductores_asignados:
                messages.error(request, '⚠️ Este conductor ya está asignado a otra unidad.')
                return redirect('panel:unidades')
            
            data['activo'] = True
            res, err = client.create_unidad(data)
            if res:
                messages.success(request, '✅ Unidad registrada exitosamente.')
            else:
                messages.error(request, err or 'Error al registrar la unidad.')
                
        elif action == 'update':
            conductor_anterior = context['unidad_conductor_map'].get(str(id_target))
            
            # Validar solo si se está ASIGNANDO un conductor nuevo (no si se está quitando)
            if nuevo_conductor_id is not None and nuevo_conductor_id != conductor_anterior:
                if nuevo_conductor_id in conductores_asignados:
                    messages.error(request, '⚠️ Este conductor ya está asignado a otra unidad.')
                    return redirect('panel:unidades')

            res, err = client.update_unidad(id_target, data)
            if res:
                # Mensaje claro para confirmar si se desasignó o se cambió
                if nuevo_conductor_id is None:
                    messages.success(request, '✅ Conductor desasignado exitosamente.')
                else:
                    messages.success(request, '✅ Asignación de conductor actualizada.')
            else:
                messages.error(request, f'Error al actualizar: {err}')
                
        elif action == 'toggle_activo':
            nuevo_estado = request.POST.get('nuevo_estado') == 'true'
            res, err = client.toggle_unidad_activo(id_target, nuevo_estado)
            if res:
                estado_texto = "activada" if nuevo_estado else "desactivada"
                messages.success(request, f'✅ Unidad {estado_texto} exitosamente.')
            else:
                messages.error(request, err or 'Error al cambiar estado.')
        
        return redirect('panel:unidades')

    context['unidades'] = todas_unidades
    return render(request, 'panel/unidades.html', context)

def conductores_view(request):
    """Vista de gestión de conductores"""
    token = request.session.get('access_token')
    client = APIClient.from_request(request)
    user_data = request.user_data
    is_admin = user_data.get('rol_nombre') == 'ADMINISTRADOR'
    context = {'user_data': user_data, 'is_admin': is_admin}

    if request.method == 'POST' and is_admin:
        action = request.POST.get('action')
        id_target = request.POST.get('id_conductor')

        # Manejo de archivo de imagen
        licencia_imagen = request.FILES.get('licencia_imagen')

        data = {
            'nombre': request.POST.get('nombre', '').strip(),
            'dui': request.POST.get('dui', '').strip() or None,
            'licencia': request.POST.get('licencia', '').strip() or None,
            'tipo_licencia': request.POST.get('tipo_licencia', '').strip() or None,
            'telefono': request.POST.get('telefono', '').strip() or None,
        }

        if action == 'create':
            data['activo'] = True

            if licencia_imagen:
                print(f"\n📸 Archivo recibido: {licencia_imagen.name}, Tipo: {licencia_imagen.content_type}")
                res, err = client.create_conductor_with_image(data, licencia_imagen)
            else:
                res, err = client.create_conductor(data)

            if res:
                messages.success(request, '✅ Conductor registrado exitosamente.')
            else:
                print(f"\n🚨 ERROR: {err}")
                messages.error(request, f'Error: {err}')

        elif action == 'update':
            if licencia_imagen:
                res, err = client.update_conductor_with_image(id_target, data, licencia_imagen)
            else:
                res, err = client.update_conductor(id_target, data)

            if res:
                messages.success(request, '✅ Conductor actualizado exitosamente.')
            else:
                messages.error(request, err or 'Error al actualizar el conductor.')

        elif action == 'toggle_activo':
            nuevo_estado = request.POST.get('nuevo_estado') == 'true'
            res, err = client.toggle_conductor_activo(id_target, nuevo_estado)

            if res:
                estado_texto = 'activado' if nuevo_estado else 'desactivado'
                messages.success(request, f'✅ Conductor {estado_texto} exitosamente.')
            else:
                messages.error(request, err or 'Error al cambiar el estado del conductor.')

        return redirect('panel:conductores')

    # Cargar conductores
    conductores_resp, _ = client.get_conductores()
    context['conductores'] = conductores_resp.get('results', []) if conductores_resp else []

    return render(request, 'panel/conductores.html', context)


def clientes_view(request):
    """Vista de gestión de clientes con tipo y documento"""
    token = request.session.get('access_token')
    client = APIClient.from_request(request)
    user_data = request.user_data
    is_admin = user_data.get('rol_nombre') == 'ADMINISTRADOR'
    context = {'user_data': user_data, 'is_admin': is_admin}

    if request.method == 'POST' and is_admin:
        action = request.POST.get('action')
        id_target = request.POST.get('id_cliente')
        
        # Usar los nombres de campo que coinciden con la BD
        data = {
            'nombre': request.POST.get('nombre', '').strip(),
            'nombre_comercial': request.POST.get('nombre_comercial', '').strip() or None,
            'tipo_cliente': request.POST.get('tipo_cliente', '').strip() or None,
            'documento': request.POST.get('documento', '').strip() or None,
            'nit': request.POST.get('nit', '').strip() or None,
            'contacto': request.POST.get('contacto', '').strip() or None,
            'telefono': request.POST.get('telefono', '').strip() or None,
            'correo': request.POST.get('correo', '').strip() or None,  # Usar 'correo'
            'direccion': request.POST.get('direccion', '').strip() or None,
        }

        if action == 'create':
            data['activo'] = True
            res, err = client.create_cliente(data)
            if res:
                messages.success(request, '✅ Cliente registrado exitosamente.')
            else:
                messages.error(request, err or 'Error al registrar el cliente.')
                
        elif action == 'update':
            res, err = client.update_cliente(id_target, data)
            if res:
                messages.success(request, '✅ Cliente actualizado exitosamente.')
            else:
                messages.error(request, err or 'Error al actualizar el cliente.')
                
        elif action == 'toggle_activo':
            nuevo_estado = request.POST.get('nuevo_estado') == 'true'
            res, err = client.toggle_cliente_activo(id_target, nuevo_estado)
            if res:
                estado_texto = "activado" if nuevo_estado else "desactivado"
                messages.success(request, f'✅ Cliente {estado_texto} exitosamente.')
            else:
                messages.error(request, err or 'Error al cambiar estado.')
        
        return redirect('panel:clientes')

    # Cargar clientes
    clientes_resp, _ = client.get_clientes()
    context['clientes'] = clientes_resp.get('results', []) if clientes_resp else []
    
    return render(request, 'panel/clientes.html', context)


def viajes_view(request):
    """Vista de programación, edición, eliminación y consulta de viajes"""
    token = request.session.get('access_token')
    client = APIClient.from_request(request)
    user_data = request.user_data
    is_admin = user_data.get('rol_nombre') == 'ADMINISTRADOR'
    context = {'user_data': user_data, 'is_admin': is_admin}

    try:
        # Cargar datos para el formulario
        unidades, _ = client.get_unidades()
        context['unidades'] = [u for u in (unidades.get('results', []) if unidades else []) if u.get('activo')]

        tipos_unidad, _ = client.get_tipos_unidad()
        context['tipos_unidad'] = tipos_unidad.get('results', []) if tipos_unidad else []

        conductores, _ = client.get_conductores()
        context['conductores'] = [c for c in (conductores.get('results', []) if conductores else []) if c.get('activo')]

        clientes, _ = client.get_clientes()
        context['clientes'] = [c for c in (clientes.get('results', []) if clientes else []) if c.get('activo')]

        ubicaciones, ubicaciones_error = client.get_all_pages('viajes/ubicaciones')
        context['ubicaciones'] = ubicaciones.get('results', []) if ubicaciones else []
        context['departamentos_ubicaciones'] = sorted({
            (ubicacion.get('departamento') or '').strip()
            for ubicacion in context['ubicaciones']
            if (ubicacion.get('departamento') or '').strip()
        })
        if ubicaciones_error:
            messages.error(request, f'No se pudieron cargar todas las ubicaciones: {ubicaciones_error}')
        context['routing_api_url'] = getattr(
            settings,
            'ROUTING_API_URL',
            'https://router.project-osrm.org',
        )

        # Cargar TODAS las cargas
        todas_cargas, _ = client.get_cargas()
        todas_cargas_data = todas_cargas.get('results', []) if todas_cargas else []

        # Separar cargas disponibles y cargas ya asignadas a otros viajes
        context['cargas_disponibles'] = [c for c in todas_cargas_data if not c.get('id_viaje')]
        context['todas_cargas'] = todas_cargas_data  # Para uso interno (editar)
    except Exception as e:
        messages.error(request, f'Error al cargar datos: {str(e)}')
        context['unidades'] = []
        context['tipos_unidad'] = []
        context['conductores'] = []
        context['clientes'] = []
        context['ubicaciones'] = []
        context['cargas_disponibles'] = []
        context['todas_cargas'] = []

    if request.method == 'POST' and is_admin:
        action = request.POST.get('action')
        id_target = request.POST.get('id_viaje')

        def safe_int_or_none(value):
            if value is None or value == '' or value == 'None':
                return None
            try:
                return int(value)
            except (ValueError, TypeError):
                return None

        def safe_float_or_none(value):
            if value is None or str(value).strip() == '':
                return None
            try:
                return float(value)
            except (ValueError, TypeError):
                return None

        if action == 'create':
            data = {
                'correlativo': request.POST.get('correlativo', '').strip().upper(),
                'id_unidad': safe_int_or_none(request.POST.get('id_unidad')),
                'id_conductor': safe_int_or_none(request.POST.get('id_conductor')),
                'id_cliente': safe_int_or_none(request.POST.get('id_cliente')),
                'id_origen': safe_int_or_none(request.POST.get('id_origen')),
                'id_destino': safe_int_or_none(request.POST.get('id_destino')),
                'id_estado_viaje': 1,
                'fecha_programada': request.POST.get('fecha_salida') or None,
                'fecha_salida': request.POST.get('fecha_salida') or None,
                'fecha_llegada_est': request.POST.get('fecha_llegada_est') or None,
                'distancia_km': safe_float_or_none(request.POST.get('distancia_km')),
                'polyline_ruta': request.POST.get('polyline_ruta', '').strip() or None,
                'observaciones': request.POST.get('observaciones', '').strip() or None,
                'cargas': list(dict.fromkeys(request.POST.getlist('cargas'))),
            }

            res, err = client.create_viaje(data)
            if res:
                messages.success(request, '✅ Viaje registrado exitosamente.')
            else:
                messages.error(request, f'⚠️ No se pudo crear el viaje: {err}')

        elif action == 'update':
            cargas_seleccionadas = list(dict.fromkeys(
                request.POST.getlist('cargas_existentes') + request.POST.getlist('cargas')
            ))
            data = {
                'correlativo': request.POST.get('correlativo', '').strip().upper(),
                'id_unidad': safe_int_or_none(request.POST.get('id_unidad')),
                'id_cliente': safe_int_or_none(request.POST.get('id_cliente')),
                'id_origen': safe_int_or_none(request.POST.get('id_origen')),
                'id_destino': safe_int_or_none(request.POST.get('id_destino')),
                'fecha_programada': request.POST.get('fecha_salida') or None,
                'fecha_salida': request.POST.get('fecha_salida') or None,
                'fecha_llegada_est': request.POST.get('fecha_llegada_est') or None,
                'distancia_km': safe_float_or_none(request.POST.get('distancia_km')),
                'polyline_ruta': request.POST.get('polyline_ruta', '').strip() or None,
                'observaciones': request.POST.get('observaciones', '').strip() or None,
                'cargas': cargas_seleccionadas,
            }

            res, err = client.update_viaje(id_target, data)
            if res:
                messages.success(request, '✅ Viaje y sus cargas actualizados exitosamente.')
            else:
                messages.error(request, err or 'Error al actualizar el viaje.')

        elif action == 'delete':
            # La API ya se encarga de liberar la unidad y las cargas automáticamente
            res, err = client.delete_viaje(id_target)
            if res:
                messages.success(request, '✅ Viaje eliminado exitosamente. La unidad y las cargas han sido liberadas.')
            else:
                messages.error(request, f'⚠️ Error al eliminar: {err}')

        elif action == 'cancelar':
            res, err = client.update_viaje(id_target, {'id_estado_viaje': 4})
            if res:
                messages.success(request, 'Viaje cancelado. Sus cargas quedaron disponibles.')
            else:
                messages.error(request, err or 'No se pudo cancelar el viaje.')

        return redirect('panel:viajes')

    # Consultar viajes registrados
    try:
        viajes, _ = client.get_viajes()
        context['viajes'] = viajes.get('results', []) if viajes else []
    except Exception as e:
        messages.error(request, f'Error al cargar viajes: {str(e)}')
        context['viajes'] = []

    return render(request, 'panel/viajes.html', context)


def cargas_view(request):
    """Vista de gestión de cargas (independiente de viajes)"""
    token = request.session.get('access_token')
    client = APIClient.from_request(request)
    user_data = request.user_data
    is_admin = user_data.get('rol_nombre') == 'ADMINISTRADOR'
    context = {'user_data': user_data, 'is_admin': is_admin}

    # Cargar tipos de carga y clientes para los selectores
    tipos_carga, _ = client.get_tipos_carga()
    context['tipos_carga'] = tipos_carga.get('results', []) if tipos_carga else []

    clientes, _ = client.get_clientes()
    context['clientes'] = clientes.get('results', []) if clientes else []

    if request.method == 'POST' and is_admin:
        action = request.POST.get('action')
        id_target = request.POST.get('id_carga')

        def safe_int_or_none(value):
            if value is None or value == '' or value == 'None':
                return None
            try:
                return int(value)
            except (ValueError, TypeError):
                return None

        def safe_float_or_none(value):
            if value is None or value == '' or value == 'None':
                return None
            try:
                return float(value)
            except (ValueError, TypeError):
                return None

        data = {
            'descripcion': request.POST.get('descripcion', '').strip(),
            'id_tipo_carga': safe_int_or_none(request.POST.get('id_tipo_carga')),
            'id_cliente': safe_int_or_none(request.POST.get('id_cliente')),
            'cantidad': safe_int_or_none(request.POST.get('cantidad')),
            'unidad_medida': request.POST.get('unidad_medida', '').strip(),
            'peso_ton': safe_float_or_none(request.POST.get('peso_ton')),
            'documento_ref': request.POST.get('documento_ref', '').strip(),
        }

        if action == 'create':
            res, err = client.create_carga(data)
            if res:
                messages.success(request, '✅ Carga registrada exitosamente.')
            else:
                messages.error(request, err or 'Error al registrar la carga.')

        elif action == 'update':
            res, err = client.update_carga(id_target, data)
            if res:
                messages.success(request, '✅ Carga actualizada exitosamente.')
            else:
                messages.error(request, err or 'Error al actualizar la carga.')

        elif action == 'delete':
            res, err = client.delete_carga(id_target)
            if res:
                messages.success(request, '✅ Carga eliminada exitosamente.')
            else:
                messages.error(request, err or 'Error al eliminar la carga.')

        return redirect('panel:cargas')

    # Cargar todas las cargas
    cargas, _ = client.get_cargas()
    context['cargas'] = cargas.get('results', []) if cargas else []

    return render(request, 'panel/cargas.html', context)


def tipos_carga_view(request):
    """Vista de gestión de tipos de carga"""
    token = request.session.get('access_token')
    client = APIClient.from_request(request)
    user_data = request.user_data
    is_admin = user_data.get('rol_nombre') == 'ADMINISTRADOR'
    context = {'user_data': user_data, 'is_admin': is_admin}

    if request.method == 'POST' and is_admin:
        action = request.POST.get('action')
        id_target = request.POST.get('id_tipo_carga')

        data = {
            'nombre': request.POST.get('nombre', '').strip(),
            'descripcion': request.POST.get('descripcion', '').strip(),
        }

        if action == 'create':
            res, err = client.create_tipo_carga(data)
            if res:
                messages.success(request, '✅ Tipo de carga registrado exitosamente.')
            else:
                messages.error(request, err or 'Error al registrar el tipo de carga.')

        elif action == 'update':
            res, err = client.update_tipo_carga(id_target, data)
            if res:
                messages.success(request, '✅ Tipo de carga actualizado exitosamente.')
            else:
                messages.error(request, err or 'Error al actualizar el tipo de carga.')

        elif action == 'delete':
            res, err = client.delete_tipo_carga(id_target)
            if res:
                messages.success(request, '✅ Tipo de carga eliminado exitosamente.')
            else:
                messages.error(request, err or 'Error al eliminar el tipo de carga.')

        return redirect('panel:tipos_carga')

    # Cargar todos los tipos de carga
    tipos_carga, _ = client.get_tipos_carga()
    context['tipos_carga'] = tipos_carga.get('results', []) if tipos_carga else []

    return render(request, 'panel/tipos_carga.html', context)


def control_view(request):
    """Vista de control de combustible y movimientos"""
    token = request.session.get('access_token')
    client = APIClient.from_request(request)
    user_data = request.user_data
    is_admin = user_data.get('rol_nombre') == 'ADMINISTRADOR'
    context = {'user_data': user_data, 'is_admin': is_admin}

    if request.method == 'POST' and is_admin:
        action = request.POST.get('action')
        
        def safe_int_or_none(value):
            if value is None or str(value).strip() == '' or str(value).strip().lower() == 'none':
                return None
            try:
                return int(value)
            except (ValueError, TypeError):
                return None

        if action == 'registrar_recarga':
            try:
                galones = float(request.POST.get('galones', ''))
                precio = float(request.POST.get('precio_galon', ''))
                nivel_tanque = float(request.POST.get('nivel_tanque_gal', ''))
            except (TypeError, ValueError):
                messages.error(request, 'Indica los galones comprados, el nivel real del tanque y un precio válidos.')
            else:
                data = {
                    'id_unidad': safe_int_or_none(request.POST.get('id_unidad')),
                    'id_viaje': safe_int_or_none(request.POST.get('id_viaje')),
                    'fecha_hora': request.POST.get('fecha_hora'),
                    'galones': galones,
                    'nivel_tanque_gal': nivel_tanque,
                    'precio_galon': precio,
                    'lugar': request.POST.get('lugar', '').strip() or None,
                    'numero_factura': request.POST.get('numero_factura', '').strip() or None,
                }
                res, err = client.create_recarga(data)
                if res:
                    messages.success(request, '✅ Recarga registrada exitosamente.')
                else:
                    messages.error(request, f'Error: {err}')
                
        elif action == 'registrar_movimiento':
            def clean_val(val, is_int=False):
                if val is None or str(val).strip() == '' or str(val).strip().lower() == 'none':
                    return None
                if is_int:
                    try:
                        return int(val)
                    except:
                        return None
                return str(val).strip()

            data = {
                'id_unidad': clean_val(request.POST.get('id_unidad'), is_int=True),
                'id_ubicacion': clean_val(request.POST.get('id_ubicacion'), is_int=True),
                'tipo': clean_val(request.POST.get('tipo')),
                'id_viaje': clean_val(request.POST.get('id_viaje'), is_int=True),
                'id_conductor': clean_val(request.POST.get('id_conductor'), is_int=True),
                'odometro_km': clean_val(request.POST.get('odometro_km'), is_int=True),
                'observacion': clean_val(request.POST.get('observacion')),
            }

            # Manejo especial para decimal
            comb_val = request.POST.get('combustible_gal')
            if comb_val and str(comb_val).strip() != '':
                try:
                    data['combustible_gal'] = float(comb_val)
                except ValueError:
                    data['combustible_gal'] = None
            else:
                data['combustible_gal'] = None

            res, err = client.create_movimiento(data)
            if res:
                messages.success(request, f'✅ Movimiento de {data["tipo"]} registrado exitosamente.')
            else:
                messages.error(request, f'Error: {err}')
        
        return redirect('panel:control')

    # Cargar datos para formularios usando los métodos correctos de APIClient
    viajes_resp, _ = client.get_viajes()
    viajes_data = viajes_resp.get('results', []) if viajes_resp else []
    context['viajes_movimiento'] = [
        v for v in viajes_data if v.get('id_estado_viaje') in [1, 2]
    ]
    context['viajes_recarga'] = [
        v for v in viajes_data if v.get('id_estado_viaje') in [1, 2]
    ]
    context['viaje_preseleccionado'] = request.GET.get('viaje', '')
    tipo_preseleccionado = request.GET.get('tipo', '').upper()
    context['tipo_movimiento_preseleccionado'] = (
        tipo_preseleccionado if tipo_preseleccionado in ('SALIDA', 'ENTRADA') else ''
    )

    unidades_resp, _ = client.get_unidades()
    context['unidades'] = [u for u in (unidades_resp.get('results', []) if unidades_resp else []) if u.get('activo')]

    conductores_resp, _ = client.get_conductores()
    context['conductores'] = [c for c in (conductores_resp.get('results', []) if conductores_resp else []) if c.get('activo')]

    ubicaciones_resp, _ = client.get_ubicaciones()
    context['ubicaciones'] = ubicaciones_resp.get('results', []) if ubicaciones_resp else []

    # Cargar historial
    recargas_resp, _ = client.get_recargas()
    context['historial_recargas'] = recargas_resp.get('results', [])[:15] if recargas_resp else []

    movimientos_resp, _ = client.get_movimientos()
    context['historial_movimientos'] = movimientos_resp.get('results', [])[:15] if movimientos_resp else []

    return render(request, 'panel/control.html', context)


def seguimiento_gps_view(request):
    """Mapa de rutas planeadas y últimas posiciones GPS recibidas."""
    client = APIClient.from_request(request)
    viajes_resp, viajes_error = client.get_viajes()
    ubicaciones_resp, ubicaciones_error = client.get_ubicaciones()
    posiciones_resp, posiciones_error = client.get_posiciones_gps()

    if viajes_error:
        messages.error(request, f'No se pudieron cargar los viajes: {viajes_error}')
    if ubicaciones_error:
        messages.error(request, f'No se pudieron cargar las ubicaciones: {ubicaciones_error}')
    if posiciones_error:
        messages.error(request, f'No se pudieron cargar las posiciones GPS: {posiciones_error}')

    ubicaciones = {
        str(ubicacion.get('id_ubicacion')): ubicacion
        for ubicacion in (ubicaciones_resp.get('results', []) if ubicaciones_resp else [])
    }
    posiciones = posiciones_resp.get('results', []) if posiciones_resp else []
    viajes = viajes_resp.get('results', []) if viajes_resp else []
    viajes_con_posicion = {str(posicion.get('id_viaje')) for posicion in posiciones}
    nombres_estado = {1: 'PROGRAMADO', 2: 'EN_CURSO', 3: 'COMPLETADO', 4: 'CANCELADO'}
    datos_viajes = []

    def coordenadas(ubicacion):
        try:
            return [float(ubicacion['latitud']), float(ubicacion['longitud'])]
        except (KeyError, TypeError, ValueError):
            return None

    for viaje in viajes:
        try:
            estado_id = int(viaje.get('id_estado_viaje'))
        except (TypeError, ValueError):
            estado_id = 0

        if estado_id not in (1, 2) and str(viaje.get('id_viaje')) not in viajes_con_posicion:
            continue

        origen = ubicaciones.get(str(viaje.get('id_origen')), {})
        destino = ubicaciones.get(str(viaje.get('id_destino')), {})
        datos_viajes.append({
            'id': viaje.get('id_viaje'),
            'correlativo': viaje.get('correlativo') or f"Viaje {viaje.get('id_viaje')}",
            'unidad': viaje.get('unidad_placa') or 'Sin unidad',
            'conductor': viaje.get('conductor_nombre') or 'Sin conductor',
            'estado': nombres_estado.get(estado_id, 'DESCONOCIDO'),
            'origen_nombre': viaje.get('origen_nombre') or origen.get('nombre') or 'Origen',
            'destino_nombre': viaje.get('destino_nombre') or destino.get('nombre') or 'Destino',
            'origen': coordenadas(origen),
            'destino': coordenadas(destino),
            'distancia_km': viaje.get('distancia_km'),
            'polyline': viaje.get('polyline_ruta') or '',
            'fecha_programada': viaje.get('fecha_programada'),
            'fecha_salida': viaje.get('fecha_salida'),
            'fecha_llegada_est': viaje.get('fecha_llegada_est'),
        })

    datos_posiciones = []
    for posicion in posiciones:
        try:
            datos_posiciones.append({
                'id_viaje': posicion.get('id_viaje'),
                'latitud': float(posicion['latitud']),
                'longitud': float(posicion['longitud']),
                'velocidad_kmh': float(posicion['velocidad_kmh']) if posicion.get('velocidad_kmh') is not None else None,
                'rumbo': posicion.get('rumbo'),
                'fecha_hora': posicion.get('fecha_hora'),
            })
        except (KeyError, TypeError, ValueError):
            continue

    return render(request, 'panel/seguimiento_gps.html', {
        'user_data': request.user_data,
        'tracking_data': {'viajes': datos_viajes, 'posiciones': datos_posiciones},
        'routing_api_url': getattr(settings, 'ROUTING_API_URL', 'https://router.project-osrm.org'),
    })


def reportes_view(request):
    """Resumen de flota e historial consultable de viajes."""
    client = APIClient.from_request(request)
    filtros = {
        key: request.GET.get(key, '').strip()
        for key in ('buscar', 'unidad', 'conductor', 'estado', 'desde', 'hasta')
    }
    filtros_api = {key: value for key, value in filtros.items() if value}

    resumen, resumen_error = client.get_reporte_panel()
    rendimiento, rendimiento_error = client.get_reporte_rendimiento()
    historial, historial_error = client.get_historial_viajes(filtros_api)
    unidades_resp, unidades_error = client.get_unidades()
    conductores_resp, conductores_error = client.get_conductores()

    for error in (resumen_error, rendimiento_error, historial_error, unidades_error, conductores_error):
        if error:
            messages.error(request, error)

    return render(request, 'panel/reportes.html', {
        'user_data': request.user_data,
        'resumen': resumen or {},
        'rendimiento': rendimiento or {},
        'historial': historial if isinstance(historial, list) else [],
        'unidades': unidades_resp.get('results', []) if unidades_resp else [],
        'conductores': conductores_resp.get('results', []) if conductores_resp else [],
        'filtros': filtros,
    })