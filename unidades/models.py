from django.db import models

class TipoUnidad(models.Model):
    id_tipo_unidad = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=150, blank=True)

    class Meta:
        db_table = 'tipo_unidad'

    def __str__(self):
        return self.nombre


class EstadoUnidad(models.Model):
    id_estado_unidad = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = 'estado_unidad'

    def __str__(self):
        return self.nombre


class Conductor(models.Model):
    id_conductor = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    dui = models.CharField(max_length=20, unique=True, blank=True, null=True)
    licencia = models.CharField(max_length=50, blank=True, null=True)  # ✅ Sin unique=True
    tipo_licencia = models.CharField(max_length=50, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'conductor'

    def __str__(self):
        return self.nombre


class DispositivoGPS(models.Model):
    id_dispositivo = models.AutoField(primary_key=True)
    numero_serie = models.CharField(max_length=50, unique=True)
    modelo = models.CharField(max_length=50, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'dispositivo_gps'

    def __str__(self):
        return self.numero_serie


class Unidad(models.Model):
    id_unidad = models.AutoField(primary_key=True)
    placa = models.CharField(max_length=20, unique=True)
    codigo_interno = models.CharField(max_length=20, unique=True)
    
    # Relaciones
    id_tipo_unidad = models.ForeignKey('TipoUnidad', on_delete=models.CASCADE, db_column='id_tipo_unidad')
    id_estado_unidad = models.ForeignKey('EstadoUnidad', on_delete=models.CASCADE, db_column='id_estado_unidad')
    
    # ✅ ESTE ES EL CAMPO QUE NECESITAMOS (ya lo agregamos en la BD en el Paso 1)
    id_conductor = models.ForeignKey('Conductor', on_delete=models.SET_NULL, null=True, blank=True, db_column='id_conductor', related_name='unidades_asignadas')
    
    # Otros campos
    capacidad_ton = models.DecimalField(max_digits=8, decimal_places=2)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'unidad'

    def __str__(self):
        return f"{self.placa} - {self.codigo_interno}"

class AsignacionUnidad(models.Model):
    id_asignacion = models.AutoField(primary_key=True)
    id_unidad = models.ForeignKey(Unidad, on_delete=models.CASCADE, db_column='id_unidad')
    id_conductor = models.ForeignKey(Conductor, on_delete=models.CASCADE, db_column='id_conductor')
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        db_table = 'asignacion_unidad'

    def __str__(self):
        return f"{self.id_unidad.placa} -> {self.id_conductor.nombre}"


class Mantenimiento(models.Model):
    id_mantenimiento = models.AutoField(primary_key=True)
    id_unidad = models.ForeignKey(Unidad, on_delete=models.CASCADE, db_column='id_unidad')
    tipo = models.CharField(max_length=50)
    descripcion = models.TextField(blank=True)
    fecha = models.DateTimeField()
    costo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'mantenimiento'

    def __str__(self):
        return f"{self.tipo} - {self.id_unidad.placa}"