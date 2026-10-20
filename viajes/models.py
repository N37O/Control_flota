from django.db import models
from unidades.models import Unidad, Conductor

class Ubicacion(models.Model):
    id_ubicacion = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    departamento = models.CharField(max_length=50, blank=True)
    direccion = models.CharField(max_length=200, blank=True)
    latitud = models.DecimalField(max_digits=9, decimal_places=6)
    longitud = models.DecimalField(max_digits=9, decimal_places=6)
    es_base = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'ubicacion'
        unique_together = ('nombre', 'departamento')

    def __str__(self):
        return f"{self.nombre}, {self.departamento}"

class Cliente(models.Model):
    id_cliente = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=120)
    nit = models.CharField(max_length=20, blank=True)
    contacto = models.CharField(max_length=100, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    correo = models.CharField(max_length=120, blank=True)
    direccion = models.CharField(max_length=200, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'cliente'

    def __str__(self):
        return self.nombre

class TipoCarga(models.Model):
    id_tipo_carga = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=60, unique=True)
    requiere_refrigeracion = models.BooleanField(default=False)
    es_peligrosa = models.BooleanField(default=False)

    class Meta:
        db_table = 'tipo_carga'

    def __str__(self):
        return self.nombre

class EstadoViaje(models.Model):
    id_estado_viaje = models.AutoField(primary_key=True)
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=40)

    class Meta:
        db_table = 'estado_viaje'

    def __str__(self):
        return self.nombre

class Viaje(models.Model):
    id_viaje = models.AutoField(primary_key=True)
    correlativo = models.CharField(max_length=20, unique=True)
    id_unidad = models.ForeignKey(Unidad, on_delete=models.CASCADE, db_column='id_unidad')
    id_conductor = models.ForeignKey(Conductor, on_delete=models.CASCADE, db_column='id_conductor')
    id_origen = models.ForeignKey(Ubicacion, on_delete=models.CASCADE, related_name='viajes_origen', db_column='id_origen')
    id_destino = models.ForeignKey(Ubicacion, on_delete=models.CASCADE, related_name='viajes_destino', db_column='id_destino')
    id_estado_viaje = models.ForeignKey(EstadoViaje, on_delete=models.CASCADE, db_column='id_estado_viaje')
    distancia_km = models.DecimalField(max_digits=8, decimal_places=2)
    polyline_ruta = models.TextField(blank=True, null=True)
    fecha_programada = models.DateTimeField(null=True, blank=True)
    fecha_salida = models.DateTimeField(null=True, blank=True)
    fecha_llegada_est = models.DateTimeField(null=True, blank=True)
    fecha_llegada_real = models.DateTimeField(null=True, blank=True)
    odometro_salida = models.IntegerField(null=True, blank=True)
    odometro_llegada = models.IntegerField(null=True, blank=True)
    combustible_salida_gal = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    combustible_llegada_gal = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    precio_galon = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    observaciones = models.CharField(max_length=255, blank=True)
    # Campo agregado desde base.txt
    id_usuario_registro = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL, null=True, blank=True, db_column='id_usuario_registro')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'viaje'

    def __str__(self):
        return self.correlativo

class Carga(models.Model):
    id_carga = models.AutoField(primary_key=True)
    id_viaje = models.ForeignKey(Viaje, on_delete=models.CASCADE, db_column='id_viaje')
    id_tipo_carga = models.ForeignKey(TipoCarga, on_delete=models.CASCADE, db_column='id_tipo_carga')
    id_cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, null=True, blank=True, db_column='id_cliente')
    descripcion = models.CharField(max_length=150, blank=True)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unidad_medida = models.CharField(max_length=15, default='TON')
    peso_ton = models.DecimalField(max_digits=8, decimal_places=2)
    documento_ref = models.CharField(max_length=40, blank=True)

    class Meta:
        db_table = 'carga'

class Movimiento(models.Model):
    # Cambiado a BigAutoField porque en la BD es BIGINT UNSIGNED
    id_movimiento = models.BigAutoField(primary_key=True)
    id_viaje = models.ForeignKey(Viaje, on_delete=models.CASCADE, null=True, blank=True, db_column='id_viaje')
    id_unidad = models.ForeignKey(Unidad, on_delete=models.CASCADE, db_column='id_unidad')
    id_conductor = models.ForeignKey(Conductor, on_delete=models.CASCADE, null=True, blank=True, db_column='id_conductor')
    id_ubicacion = models.ForeignKey(Ubicacion, on_delete=models.CASCADE, db_column='id_ubicacion')
    tipo = models.CharField(max_length=10, choices=[('SALIDA', 'Salida'), ('ENTRADA', 'Entrada')])
    fecha_hora = models.DateTimeField()
    combustible_gal = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    odometro_km = models.IntegerField(null=True, blank=True)
    # Campo agregado desde base.txt
    id_usuario_registro = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL, null=True, blank=True, db_column='id_usuario_registro')
    observacion = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = 'movimiento'

class RecargaCombustible(models.Model):
    id_recarga = models.AutoField(primary_key=True)
    id_viaje = models.ForeignKey(Viaje, on_delete=models.CASCADE, db_column='id_viaje')
    fecha_hora = models.DateTimeField()
    galones = models.DecimalField(max_digits=6, decimal_places=2)
    precio_galon = models.DecimalField(max_digits=6, decimal_places=3)
    lugar = models.CharField(max_length=100, blank=True)
    numero_factura = models.CharField(max_length=40, blank=True)

    class Meta:
        db_table = 'recarga_combustible'

class PosicionGPS(models.Model):
    # Cambiado a BigAutoField porque en la BD es BIGINT UNSIGNED
    id_posicion = models.BigAutoField(primary_key=True)
    id_dispositivo = models.ForeignKey('unidades.DispositivoGPS', on_delete=models.CASCADE, db_column='id_dispositivo')
    id_viaje = models.ForeignKey(Viaje, on_delete=models.CASCADE, null=True, blank=True, db_column='id_viaje')
    latitud = models.DecimalField(max_digits=9, decimal_places=6)
    longitud = models.DecimalField(max_digits=9, decimal_places=6)
    velocidad_kmh = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rumbo = models.SmallIntegerField(null=True, blank=True)
    fecha_hora = models.DateTimeField()
    recibido_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'posicion_gps'

class Alerta(models.Model):
    # Cambiado a BigAutoField porque en la BD es BIGINT UNSIGNED
    id_alerta = models.BigAutoField(primary_key=True)
    id_viaje = models.ForeignKey(Viaje, on_delete=models.CASCADE, null=True, blank=True, db_column='id_viaje')
    id_unidad = models.ForeignKey(Unidad, on_delete=models.CASCADE, null=True, blank=True, db_column='id_unidad')
    tipo = models.CharField(max_length=30)
    mensaje = models.CharField(max_length=255)
    # CORREGIDO: max_length=11 para que quepa 'ADVERTENCIA'
    severidad = models.CharField(max_length=11, choices=[('INFO', 'Info'), ('ADVERTENCIA', 'Advertencia'), ('CRITICA', 'Crítica')], default='ADVERTENCIA')
    fecha = models.DateTimeField(auto_now_add=True)
    atendida = models.BooleanField(default=False)
    # Campo agregado desde base.txt
    atendida_por = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL, null=True, blank=True, db_column='atendida_por')

    class Meta:
        db_table = 'alerta'