from rest_framework import views, permissions, status
from rest_framework.response import Response
from django.db.models import Sum, Avg, Count, F, ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce
from viajes.models import Viaje, Carga, Movimiento, RecargaCombustible
from unidades.models import Unidad

class PanelFlotaView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        unidades_disponibles = Unidad.objects.filter(
            id_estado_unidad__codigo='DISPONIBLE', activo=True
        ).count()
        
        unidades_transito = Unidad.objects.filter(
            id_estado_unidad__codigo='EN_VIAJE', activo=True
        ).count()
        
        viajes_programados = Viaje.objects.filter(
            id_estado_viaje__codigo='PROGRAMADO'
        ).count()
        
        viajes_transito = Viaje.objects.filter(
            id_estado_viaje__codigo='EN_TRANSITO'
        ).count()
        
        alertas_pendientes = Viaje.objects.filter(
            id_estado_viaje__codigo='EN_TRANSITO',
            fecha_llegada_est__lt=timezone.now()
        ).count()

        return Response({
            'unidades_disponibles': unidades_disponibles,
            'unidades_transito': unidades_transito,
            'viajes_programados': viajes_programados,
            'viajes_transito': viajes_transito,
            'alertas_pendientes': alertas_pendientes,
        })

class RendimientoView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        viajes = Viaje.objects.filter(
            id_estado_viaje__codigo='COMPLETADO',
            combustible_llegada_gal__isnull=False
        ).annotate(
            galones_consumidos=ExpressionWrapper(
                F('combustible_salida_gal') - F('combustible_llegada_gal'),
                output_field=DecimalField()
            ),
            rendimiento=ExpressionWrapper(
                F('distancia_km') / (F('combustible_salida_gal') - F('combustible_llegada_gal')),
                output_field=DecimalField()
            )
        )

        rendimiento_promedio = viajes.aggregate(
            avg_rendimiento=Avg('rendimiento')
        )['avg_rendimiento']

        return Response({
            'rendimiento_promedio': round(rendimiento_promedio, 2) if rendimiento_promedio else 0,
            'total_viajes': viajes.count()
        })

class HistorialView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        viajes = Viaje.objects.all().select_related(
            'id_unidad', 'id_conductor', 'id_origen', 'id_destino', 'id_estado_viaje'
        )
        
        # Filtros
        if request.query_params.get('unidad'):
            viajes = viajes.filter(id_unidad=request.query_params.get('unidad'))
        if request.query_params.get('conductor'):
            viajes = viajes.filter(id_conductor=request.query_params.get('conductor'))
        if request.query_params.get('estado'):
            viajes = viajes.filter(id_estado_viaje=request.query_params.get('estado'))
        
        serializer_data = []
        for viaje in viajes[:50]:
            serializer_data.append({
                'correlativo': viaje.correlativo,
                'unidad': viaje.id_unidad.placa,
                'conductor': viaje.id_conductor.nombre,
                'origen': viaje.id_origen.nombre,
                'destino': viaje.id_destino.nombre,
                'estado': viaje.id_estado_viaje.nombre,
                'fecha_salida': viaje.fecha_salida,
                'fecha_llegada_est': viaje.fecha_llegada_est,
                'fecha_llegada_real': viaje.fecha_llegada_real,
            })
        
        return Response(serializer_data)