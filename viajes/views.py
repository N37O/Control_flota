from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Sum, Avg, Count
from .models import (Ubicacion, Cliente, TipoCarga, EstadoViaje, Viaje, 
                     Carga, Movimiento, RecargaCombustible, PosicionGPS, Alerta)
from .serializers import (UbicacionSerializer, ClienteSerializer, TipoCargaSerializer,
                          EstadoViajeSerializer, ViajeSerializer, CargaSerializer,
                          MovimientoSerializer, RecargaCombustibleSerializer,
                          PosicionGPSSerializer, AlertaSerializer)

class UbicacionViewSet(viewsets.ModelViewSet):
    queryset = Ubicacion.objects.filter(activo=True)
    serializer_class = UbicacionSerializer
    permission_classes = [permissions.IsAuthenticated]

class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.filter(activo=True)
    serializer_class = ClienteSerializer
    permission_classes = [permissions.IsAuthenticated]

class TipoCargaViewSet(viewsets.ModelViewSet):
    queryset = TipoCarga.objects.all()
    serializer_class = TipoCargaSerializer
    permission_classes = [permissions.IsAuthenticated]

class EstadoViajeViewSet(viewsets.ModelViewSet):
    queryset = EstadoViaje.objects.all()
    serializer_class = EstadoViajeSerializer
    permission_classes = [permissions.IsAuthenticated]

class ViajeViewSet(viewsets.ModelViewSet):
    queryset = Viaje.objects.all()
    serializer_class = ViajeSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def en_transito(self, request):
        viajes = self.queryset.filter(id_estado_viaje__codigo='EN_TRANSITO')
        serializer = self.get_serializer(viajes, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def programados(self, request):
        viajes = self.queryset.filter(id_estado_viaje__codigo='PROGRAMADO')
        serializer = self.get_serializer(viajes, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def iniciar(self, request, pk=None):
        viaje = self.get_object()
        viaje.fecha_salida = timezone.now()
        viaje.id_estado_viaje = EstadoViaje.objects.get(codigo='EN_TRANSITO')
        viaje.save()
        return Response({'message': 'Viaje iniciado'})

    @action(detail=True, methods=['post'])
    def completar(self, request, pk=None):
        viaje = self.get_object()
        viaje.fecha_llegada_real = timezone.now()
        viaje.id_estado_viaje = EstadoViaje.objects.get(codigo='COMPLETADO')
        viaje.save()
        return Response({'message': 'Viaje completado'})

class CargaViewSet(viewsets.ModelViewSet):
    queryset = Carga.objects.all()
    serializer_class = CargaSerializer
    permission_classes = [permissions.IsAuthenticated]

class MovimientoViewSet(viewsets.ModelViewSet):
    queryset = Movimiento.objects.all()
    serializer_class = MovimientoSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'])
    def registrar_salida(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        movimiento = serializer.save()
        
        # Actualizar viaje
        if movimiento.id_viaje:
            viaje = movimiento.id_viaje
            viaje.combustible_salida_gal = movimiento.combustible_gal
            viaje.odometro_salida = movimiento.odometro_km
            viaje.save()
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def registrar_entrada(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        movimiento = serializer.save()
        
        # Actualizar viaje
        if movimiento.id_viaje:
            viaje = movimiento.id_viaje
            viaje.combustible_llegada_gal = movimiento.combustible_gal
            viaje.odometro_llegada = movimiento.odometro_km
            viaje.fecha_llegada_real = timezone.now()
            viaje.id_estado_viaje = EstadoViaje.objects.get(codigo='COMPLETADO')
            viaje.save()
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class RecargaCombustibleViewSet(viewsets.ModelViewSet):
    queryset = RecargaCombustible.objects.all()
    serializer_class = RecargaCombustibleSerializer
    permission_classes = [permissions.IsAuthenticated]

class PosicionGPSViewSet(viewsets.ModelViewSet):
    queryset = PosicionGPS.objects.all()
    serializer_class = PosicionGPSSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'])
    def actualizar_posicion(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class AlertaViewSet(viewsets.ModelViewSet):
    queryset = Alerta.objects.all()
    serializer_class = AlertaSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def pendientes(self, request):
        alertas = self.queryset.filter(atendida=False)
        serializer = self.get_serializer(alertas, many=True)
        return Response(serializer.data)