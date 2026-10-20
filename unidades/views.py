from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import (TipoUnidad, EstadoUnidad, Unidad, DispositivoGPS, 
                     Conductor, AsignacionUnidad, Mantenimiento)
from .serializers import (TipoUnidadSerializer, EstadoUnidadSerializer, 
                          UnidadSerializer, DispositivoGPSSerializer,
                          ConductorSerializer, AsignacionUnidadSerializer,
                          MantenimientoSerializer)

class TipoUnidadViewSet(viewsets.ModelViewSet):
    queryset = TipoUnidad.objects.all()
    serializer_class = TipoUnidadSerializer
    permission_classes = [permissions.IsAuthenticated]

class EstadoUnidadViewSet(viewsets.ModelViewSet):
    queryset = EstadoUnidad.objects.all()
    serializer_class = EstadoUnidadSerializer
    permission_classes = [permissions.IsAuthenticated]

class UnidadViewSet(viewsets.ModelViewSet):
    queryset = Unidad.objects.all()
    serializer_class = UnidadSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['id_estado_unidad', 'id_tipo_unidad', 'placa']

    @action(detail=False, methods=['get'])
    def disponibles(self, request):
        unidades = self.queryset.filter(id_estado_unidad__codigo='DISPONIBLE')
        serializer = self.get_serializer(unidades, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def en_viaje(self, request):
        unidades = self.queryset.filter(id_estado_unidad__codigo='EN_VIAJE')
        serializer = self.get_serializer(unidades, many=True)
        return Response(serializer.data)

class DispositivoGPSViewSet(viewsets.ModelViewSet):
    queryset = DispositivoGPS.objects.all()
    serializer_class = DispositivoGPSSerializer
    permission_classes = [permissions.IsAuthenticated]

class ConductorViewSet(viewsets.ModelViewSet):
    queryset = Conductor.objects.all()
    serializer_class = ConductorSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['activo']

class AsignacionUnidadViewSet(viewsets.ModelViewSet):
    queryset = AsignacionUnidad.objects.all()
    serializer_class = AsignacionUnidadSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'])
    def asignar(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class MantenimientoViewSet(viewsets.ModelViewSet):
    queryset = Mantenimiento.objects.all()
    serializer_class = MantenimientoSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['id_unidad', 'tipo']