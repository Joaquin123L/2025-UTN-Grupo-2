# academics/models.py
from django.conf import settings
from django.db import models

Usuario = settings.AUTH_USER_MODEL


class Materia(models.Model):
    nombre = models.CharField(max_length=120, unique=True)
    eliminado = models.BooleanField(default=False)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Comision(models.Model):
    nombre = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class MateriaComisionAnio(models.Model):
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE)
    comision = models.ForeignKey(Comision, on_delete=models.CASCADE)
    anio = models.PositiveSmallIntegerField()

    titular = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="materias_como_titular"
    )
    jtp = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="materias_como_jtp"
    )
    ayudante = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="materias_como_ayudante"
    )

    class Meta:
        unique_together = ("materia", "comision", "anio")
        ordering = ["-anio", "materia__nombre", "comision__nombre"]

    def __str__(self):
        return f"{self.materia} — {self.comision} [{self.anio}]"
