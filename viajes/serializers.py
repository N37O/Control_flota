from rest_framework import serializers
from .models import (Ubicacion, Cliente, TipoCarga, EstadoViaje, Viaje, 
                     Carga, Movimiento, RecargaCombustible, PosicionGPS, Alerta)

class UbicacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ubicacion
        fields = '__all__'

class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = '__all__'

class TipoCargaSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoCarga
        fields = '__all__'

class EstadoViajeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoViaje
        fields = '__all__'

class CargaSerializer(serializers.ModelSerializer):
    tipo_carga_nombre = serializers.CharField(source='id_tipo_carga.nombre', read_only=True)
    cliente_nombre = serializers.CharField(source='id_cliente.nombre', read_only=True)

    class Meta:
        model = Carga
        fields = '__all__'
        read_only_fields = ['tipo_carga_nombre', 'cliente_nombre']

class MovimientoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Movimiento
        fields = '__all__'

class RecargaCombustibleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecargaCombustible
        fields = '__all__'

class PosicionGPSSerializer(serializers.ModelSerializer):
    class Meta:
        model = PosicionGPS
        fields = '__all__'

class AlertaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alerta
        fields = '__all__'

class ViajeSerializer(serializers.ModelSerializer):
    unidad_placa = serializers.CharField(source='id_unidad.placa', read_only=True)
    conductor_nombre = serializers.CharField(source='id_conductor.nombre', read_only=True)
    origen_nombre = serializers.CharField(source='id_origen.nombre', read_only=True)
    destino_nombre = serializers.CharField(source='id_destino.nombre', read_only=True)
    estado_nombre = serializers.CharField(source='id_estado_viaje.nombre', read_only=True)
    cargas = CargaSerializer(source='carga_set', many=True, read_only=True)

    class Meta:
        model = Viaje
        fields = '__all__'
        read_only_fields = ['unidad_placa', 'conductor_nombre', 'origen_nombre', 
                          'destino_nombre', 'estado_nombre', 'cargas']