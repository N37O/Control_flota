from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import requests

from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.utils import timezone
from django.urls import reverse

from panel.services import APIClient
from panel.views import dashboard_view, reportes_view, seguimiento_gps_view, viajes_view


class PaginatedAPIClientTests(SimpleTestCase):
    def test_get_all_pages_combines_every_result_page(self):
        first_page = Mock(status_code=200)
        first_page.json.return_value = {
            'count': 2,
            'next': 'https://api.example.test/viajes/?page=2',
            'results': [{'id': 1}],
        }
        second_page = Mock(status_code=200)
        second_page.json.return_value = {
            'count': 2,
            'next': None,
            'results': [{'id': 2}],
        }
        client = APIClient()

        with patch.object(
            client.session,
            'get',
            side_effect=[first_page, second_page],
        ) as get_mock:
            data, error = client.get_all_pages('viajes/viajes')

        self.assertIsNone(error)
        self.assertEqual(data, {'count': 2, 'results': [{'id': 1}, {'id': 2}]})
        self.assertEqual(get_mock.call_args_list[0].kwargs['params'], {'page': 1})
        self.assertEqual(get_mock.call_args_list[1].kwargs['params'], {'page': 2})


class DashboardViewTests(SimpleTestCase):
    def test_dashboard_uses_operational_data_and_calculates_last_30_days(self):
        request = RequestFactory().get('/')
        request.user_data = {
            'nombre': 'Operador',
            'rol_nombre': 'OPERADOR',
        }
        request.session = {'access_token': 'test-token'}
        completed_date = (timezone.now() - timedelta(days=5)).isoformat()
        old_date = (timezone.now() - timedelta(days=60)).isoformat()
        units = [
            {
                'activo': True,
                'estado_nombre': 'DISPONIBLE',
                'capacidad_tanque_gal': '100.00',
                'combustible_actual_gal': '20.00',
            },
            {
                'activo': True,
                'estado_nombre': 'EN VIAJE',
                'capacidad_tanque_gal': '100.00',
                'combustible_actual_gal': None,
            },
            {'activo': False, 'estado_nombre': 'DISPONIBLE'},
        ]
        trips = [
            {
                'id_estado_viaje': 3,
                'fecha_llegada_real': completed_date,
                'fecha_salida': completed_date,
                'km_recorridos': '100',
                'galones_consumidos': '10',
                'alerta_consumo': True,
                'correlativo': 'V-001',
            },
            {
                'id_estado_viaje': 1,
                'fecha_programada': timezone.now().isoformat(),
                'correlativo': 'V-002',
            },
            {
                'id_estado_viaje': 2,
                'fecha_salida': timezone.now().isoformat(),
                'correlativo': 'V-003',
            },
            {
                'id_estado_viaje': 3,
                'fecha_llegada_real': old_date,
                'km_recorridos': '500',
                'galones_consumidos': '25',
            },
        ]

        with patch('panel.views.APIClient') as api_client_class, patch(
            'panel.views.render', return_value=HttpResponse('ok')
        ) as render_mock:
            api_client = api_client_class.from_request.return_value
            api_client.get_all_pages.side_effect = [
                ({'results': units}, None),
                ({'results': trips}, None),
            ]

            response = dashboard_view(request)

        self.assertEqual(response.status_code, 200)
        context = render_mock.call_args.args[2]
        self.assertEqual(context['total_unidades'], 2)
        self.assertEqual(context['unidades_disponibles'], 1)
        self.assertEqual(context['unidades_en_viaje'], 1)
        self.assertEqual(context['unidades_combustible_bajo'], 1)
        self.assertEqual(context['unidades_sin_lectura'], 1)
        self.assertEqual(context['viajes_programados'], 1)
        self.assertEqual(context['viajes_en_curso'], 1)
        self.assertEqual(context['viajes_ultimos_30_dias'], 1)
        self.assertEqual(context['km_ultimos_30_dias'], Decimal('100'))
        self.assertEqual(context['rendimiento_ultimos_30_dias'], Decimal('10.00'))
        self.assertEqual([trip['correlativo'] for trip in context['viajes_con_alerta']], ['V-001'])


class APIClientErrorTests(SimpleTestCase):
    @patch('panel.services.requests.post')
    def test_refreshes_expired_access_token_and_retries_request(self, post_mock):
        refresh_response = requests.Response()
        refresh_response.status_code = 200
        refresh_response._content = b'{"access":"new-access","refresh":"new-refresh"}'
        post_mock.return_value = refresh_response
        updated_tokens = []
        client = APIClient(
            token='expired-access',
            refresh_token='current-refresh',
            on_token_refresh=lambda access, refresh: updated_tokens.append(
                (access, refresh)
            ),
        )
        expired_response = requests.Response()
        expired_response.status_code = 401
        expired_response.raw = Mock()
        expired_response.request = requests.Request(
            'GET',
            'https://api.example.test/api/usuarios/usuarios/',
            headers={'Authorization': 'Bearer expired-access'},
        ).prepare()
        retry_response = requests.Response()
        retry_response.status_code = 200
        with patch.object(client.session, 'send', return_value=retry_response) as send:
            response = client._refresh_on_unauthorized(expired_response)

        self.assertIs(response, retry_response)
        self.assertEqual(client.token, 'new-access')
        self.assertEqual(client.refresh_token, 'new-refresh')
        self.assertEqual(updated_tokens, [('new-access', 'new-refresh')])
        retry_request = send.call_args.args[0]
        self.assertEqual(retry_request.headers['Authorization'], 'Bearer new-access')
        self.assertEqual(retry_request.headers['X-Token-Retry'], '1')
        post_mock.assert_called_once_with(
            f'{client.base_url}/usuarios/token/refresh/',
            json={'refresh': 'current-refresh'},
            timeout=settings.API_TIMEOUT,
        )

    def test_does_not_retry_unauthorized_response_without_refresh_token(self):
        client = APIClient(token='expired-access')
        response = requests.Response()
        response.status_code = 401
        response.request = requests.Request(
            'GET',
            'https://api.example.test/api/usuarios/usuarios/',
        ).prepare()

        self.assertIs(client._refresh_on_unauthorized(response), response)

    def test_formats_api_validation_errors_instead_of_hiding_them(self):
        response = type('APIResponse', (), {
            'status_code': 400,
            'json': lambda self: {
                'id_unidad': ['La unidad ya tiene un viaje activo asignado.'],
                'id_conductor': ['El conductor está inactivo.'],
            },
        })()

        data, error = APIClient()._handle_response(response)

        self.assertIsNone(data)
        self.assertEqual(
            error,
            'id_unidad: La unidad ya tiene un viaje activo asignado.; '
            'id_conductor: El conductor está inactivo.',
        )

    def test_formats_api_detail_errors(self):
        response = type('APIResponse', (), {
            'status_code': 400,
            'json': lambda self: {'detail': 'El origen y el destino deben ser distintos.'},
        })()

        data, error = APIClient()._handle_response(response)

        self.assertIsNone(data)
        self.assertEqual(error, 'El origen y el destino deben ser distintos.')


class ViajesViewTests(SimpleTestCase):
    def test_lists_departments_from_registered_locations(self):
        request = RequestFactory().get('/viajes/')
        request.user_data = {'nombre': 'Admin', 'rol_nombre': 'ADMINISTRADOR'}
        request.session = {'access_token': 'test-token', 'refresh_token': 'refresh'}
        locations = [
            {'id_ubicacion': 1, 'nombre': 'Conchagua', 'departamento': 'La Unión'},
            {'id_ubicacion': 2, 'nombre': 'Usulután Centro', 'departamento': 'Usulután'},
            {'id_ubicacion': 3, 'nombre': 'La Unión', 'departamento': 'La Unión'},
        ]

        with patch('panel.views.APIClient') as api_client_class, patch(
            'panel.views.render', return_value=HttpResponse('ok')
        ) as render_mock:
            client = api_client_class.from_request.return_value
            client.get_unidades.return_value = ({'results': []}, None)
            client.get_tipos_unidad.return_value = ({'results': []}, None)
            client.get_conductores.return_value = ({'results': []}, None)
            client.get_clientes.return_value = ({'results': []}, None)
            client.get_all_pages.return_value = ({'results': locations}, None)
            client.get_cargas.return_value = ({'results': []}, None)
            client.get_viajes.return_value = ({'results': []}, None)

            response = viajes_view(request)

        self.assertEqual(response.status_code, 200)
        context = render_mock.call_args.args[2]
        self.assertEqual(context['departamentos_ubicaciones'], ['La Unión', 'Usulután'])

    def test_create_sends_calculated_route_to_api(self):
        request = RequestFactory().post('/viajes/', {
            'action': 'create',
            'correlativo': 'v-2026-001',
            'id_unidad': '1',
            'id_cliente': '',
            'id_origen': '10',
            'id_destino': '20',
            'fecha_salida': '2026-10-23T08:00',
            'fecha_llegada_est': '',
            'distancia_km': '72.35',
            'polyline_ruta': 'encoded-road-route',
            'observaciones': '',
        })
        request.user_data = {'nombre': 'Admin', 'rol_nombre': 'ADMINISTRADOR'}
        request.session = {'access_token': 'test-token', 'refresh_token': 'refresh'}

        with patch('panel.views.APIClient') as api_client_class, patch(
            'panel.views.messages.success'
        ):
            client = api_client_class.from_request.return_value
            client.get_unidades.return_value = ({'results': []}, None)
            client.get_tipos_unidad.return_value = ({'results': []}, None)
            client.get_conductores.return_value = ({'results': []}, None)
            client.get_clientes.return_value = ({'results': []}, None)
            client.get_all_pages.return_value = ({'results': []}, None)
            client.get_cargas.return_value = ({'results': []}, None)
            client.create_viaje.return_value = ({'id_viaje': 1}, None)

            response = viajes_view(request)

        self.assertEqual(response.status_code, 302)
        sent_data = client.create_viaje.call_args.args[0]
        self.assertEqual(sent_data['distancia_km'], 72.35)
        self.assertEqual(sent_data['polyline_ruta'], 'encoded-road-route')


class SeguimientoGPSViewTests(SimpleTestCase):
    def test_builds_map_data_from_trips_locations_and_gps_positions(self):
        request = RequestFactory().get('/seguimiento-gps/')
        request.user_data = {'nombre': 'Operador', 'rol_nombre': 'OPERADOR'}
        request.session = {'access_token': 'test-token'}

        trip = {
            'id_viaje': 12,
            'correlativo': 'V-012',
            'id_estado_viaje': 2,
            'id_origen': 3,
            'id_destino': 4,
            'origen_nombre': 'San Salvador',
            'destino_nombre': 'Santa Ana',
            'unidad_placa': 'P123456',
            'conductor_nombre': 'Conductor de prueba',
            'distancia_km': '65.00',
            'fecha_llegada_est': '2026-10-21T18:30:00-06:00',
        }

        with patch('panel.views.APIClient') as api_client_class, patch(
            'panel.views.render', return_value=HttpResponse('ok')
        ) as render_mock:
            api_client = api_client_class.from_request.return_value
            api_client.get_viajes.return_value = ({'results': [trip]}, None)
            api_client.get_ubicaciones.return_value = ({
                'results': [
                    {'id_ubicacion': 3, 'nombre': 'San Salvador', 'latitud': '13.692900', 'longitud': '-89.218200'},
                    {'id_ubicacion': 4, 'nombre': 'Santa Ana', 'latitud': '13.994200', 'longitud': '-89.559700'},
                ]
            }, None)
            api_client.get_posiciones_gps.return_value = ({'results': [{
                'id_viaje': 12,
                'latitud': '13.800000',
                'longitud': '-89.400000',
                'velocidad_kmh': '40.00',
                'rumbo': 180,
                'fecha_hora': '2026-10-21T17:45:00-06:00',
            }]}, None)

            response = seguimiento_gps_view(request)

        self.assertEqual(response.status_code, 200)
        template_name, context = render_mock.call_args.args[1:3]
        self.assertEqual(template_name, 'panel/seguimiento_gps.html')
        self.assertEqual(context['tracking_data']['viajes'][0]['origen'], [13.6929, -89.2182])
        self.assertEqual(context['tracking_data']['posiciones'][0]['id_viaje'], 12)


class ReportesViewTests(SimpleTestCase):
    def test_sends_active_filters_and_report_data_to_template(self):
        request = RequestFactory().get(
            '/reportes/?buscar=V-12&estado=2&desde=2026-10-01'
        )
        request.user_data = {'nombre': 'Operador', 'rol_nombre': 'OPERADOR'}
        request.session = {'access_token': 'test-token'}
        history = [{'correlativo': 'V-12', 'estado': 'EN_CURSO'}]

        with patch('panel.views.APIClient') as api_client_class, patch(
            'panel.views.render', return_value=HttpResponse('ok')
        ) as render_mock:
            api_client = api_client_class.from_request.return_value
            api_client.get_reporte_panel.return_value = ({'unidades_disponibles': 4}, None)
            api_client.get_reporte_rendimiento.return_value = ({'rendimiento_promedio': 8.5}, None)
            api_client.get_historial_viajes.return_value = (history, None)
            api_client.get_unidades.return_value = ({'results': []}, None)
            api_client.get_conductores.return_value = ({'results': []}, None)

            response = reportes_view(request)

        self.assertEqual(response.status_code, 200)
        api_client.get_historial_viajes.assert_called_once_with({
            'buscar': 'V-12', 'estado': '2', 'desde': '2026-10-01'
        })
        context = render_mock.call_args.args[2]
        self.assertEqual(context['resumen']['unidades_disponibles'], 4)
        self.assertEqual(context['historial'], history)


class ConductoresToggleTests(TestCase):
    def test_toggle_conductor_action_calls_api(self):
        session = self.client.session
        session['access_token'] = 'token-test'
        session['user_data'] = {'rol_nombre': 'ADMINISTRADOR'}
        session.save()

        with patch('panel.views.APIClient') as mock_api_cls:
            mock_client = mock_api_cls.from_request.return_value
            mock_client.toggle_conductor_activo.return_value = ({'status': 'success'}, None)

            response = self.client.post(
                reverse('panel:conductores'),
                {'action': 'toggle_activo', 'id_conductor': '7', 'nuevo_estado': 'false'}
            )

            self.assertEqual(response.status_code, 302)
            mock_client.toggle_conductor_activo.assert_called_once_with('7', False)
