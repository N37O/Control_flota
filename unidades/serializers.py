from rest_framework import serializers
from .models import (TipoUnidad, EstadoUnidad, Unidad, DispositivoGPS, 
                     Conductor, AsignacionUnidad, Mantenimiento)

class TipoUnidadSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoUnidad
        fields = '__all__'

class EstadoUnidadSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoUnidad
        fields = '__all__'

class DispositivoGPSSerializer(serializers.ModelSerializer):
    class Meta:
        model = DispositivoGPS
        fields = '__all__'

class ConductorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conductor
        fields = '__all__'

class AsignacionUnidadSerializer(serializers.ModelSerializer):
    unidad_placa = serializers.CharField(source='id_unidad.placa', read_only=True)
    conductor_nombre = serializers.CharField(source='id_conductor.nombre', read_only=True)

    class Meta:
        model = AsignacionUnidad
        fields = '__all__'
        read_only_fields = ['unidad_placa', 'conductor_nombre']

class MantenimientoSerializer(serializers.ModelSerializer):
    unidad_placa = serializers.CharField(source='id_unidad.placa', read_only=True)

    class Meta:
        model = Mantenimiento
        fields = '__all__'
        read_only_fields = ['unidad_placa']

class UnidadSerializer(serializers.ModelSerializer):
    tipo_nombre = serializers.CharField(source='id_tipo_unidad.nombre', read_only=True)
    estado_nombre = serializers.CharField(source='id_estado_unidad.nombre', read_only=True)
    conductor_nombre = serializers.CharField(source='id_conductor.nombre', read_only=True, allow_null=True)

    class Meta:
        model = Unidad
        fields = [
            'id_unidad', 'placa', 'codigo_interno', 'id_tipo_unidad',
            'id_estado_unidad', 'capacidad_ton', 'id_conductor',
            'tipo_nombre', 'estado_nombre', 'conductor_nombre', 'activo', 'creado_en'
        ]
        read_only_fields = ['creado_en']