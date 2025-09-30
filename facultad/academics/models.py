# academics/models.py
from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q

Usuario = settings.AUTH_USER_MODEL

class Department(models.Model):
    nombre = models.CharField(max_length=120, unique=True)
    imagen = models.ImageField(upload_to="departments/", blank=True, null=True)
    icono = models.CharField(max_length=4096, blank=True, null=True) 
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)
class Materia(models.Model):
    nombre = models.CharField(max_length=120, unique=True)
    eliminado = models.BooleanField(default=False)
    departamento = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="materias")
    descripcion = models.TextField(blank=True, null=True)
    icono = models.CharField(max_length=4096, blank=True, null=True)
    imagen = models.ImageField(upload_to="materias/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Comision(models.Model):
    nombre = models.CharField(max_length=120, unique=True)
    icono = models.CharField(max_length=4096, blank=True, null=True)
    imagen = models.ImageField(upload_to="materias/", blank=True, null=True)

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

class Resena(models.Model):
    alumno = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="resenas")
    mca = models.ForeignKey("academics.MateriaComisionAnio", on_delete=models.CASCADE, related_name="resenas")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["alumno", "mca"], name="uq_resena_alumno_mca"),
        ]
        indexes = [
            models.Index(fields=["mca"]),
            models.Index(fields=["alumno", "mca"]),
        ]

    def __str__(self):
        return f"Reseña de {self.alumno} sobre {self.mca}"


class ResenaItem(models.Model):
    class Target(models.TextChoices):
        MATERIA = "MATERIA", "Materia"
        COMISION = "COMISION", "Comisión"
        TITULAR = "TITULAR", "Profesor Titular"
        JTP     = "JTP",     "Jefe de Trabajos Prácticos"

    resena = models.ForeignKey(Resena, on_delete=models.CASCADE, related_name="items")
    target_type = models.CharField(max_length=16, choices=Target.choices)

    puntuacion = models.PositiveSmallIntegerField()
    comentario = models.TextField(blank=True)

    materia = models.ForeignKey(
        "academics.Materia", on_delete=models.CASCADE, null=True, blank=True, related_name="resenas_items"
    )
    comision = models.ForeignKey(
        "academics.Comision", on_delete=models.CASCADE, null=True, blank=True, related_name="resenas_items"
    )
    titular = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, null=True, blank=True, related_name="resenas_como_titular"
    )
    jtp = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, null=True, blank=True, related_name="resenas_como_jtp"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["resena", "target_type"], name="uq_item_por_tipo_por_resena"),

            models.CheckConstraint(
                check=Q(puntuacion__gte=1) & Q(puntuacion__lte=5),
                name="chk_item_puntuacion_1_5"
            ),

            models.CheckConstraint(
                check=(
                    (Q(target_type="MATERIA") & Q(materia__isnull=False) &
                     Q(comision__isnull=True) & Q(titular__isnull=True) & Q(jtp__isnull=True))
                    | ~Q(target_type="MATERIA")
                ),
                name="chk_item_materia_fk"
            ),

            models.CheckConstraint(
                check=(
                    (Q(target_type="COMISION") & Q(comision__isnull=False) &
                     Q(materia__isnull=True) & Q(titular__isnull=True) & Q(jtp__isnull=True))
                    | ~Q(target_type="COMISION")
                ),
                name="chk_item_comision_fk"
            ),

            models.CheckConstraint(
                check=(
                    (Q(target_type="TITULAR") & Q(titular__isnull=False) &
                     Q(materia__isnull=True) & Q(comision__isnull=True) & Q(jtp__isnull=True))
                    | ~Q(target_type="TITULAR")
                ),
                name="chk_item_titular_fk"
            ),

            models.CheckConstraint(
                check=(
                    (Q(target_type="JTP") & Q(jtp__isnull=False) &
                     Q(materia__isnull=True) & Q(comision__isnull=True) & Q(titular__isnull=True))
                    | ~Q(target_type="JTP")
                ),
                name="chk_item_jtp_fk"
            ),
        ]
        indexes = [
            models.Index(fields=["target_type"]),
        ]

    def __str__(self):
        return f"{self.target_type} [{self.puntuacion}]"

    def clean(self):
        mca = self.resena.mca

        if self.target_type == self.Target.MATERIA:
            if not self.materia_id or self.materia_id != mca.materia_id:
                raise ValidationError("La materia del item no coincide con la de la cursada (MCA).")

        elif self.target_type == self.Target.COMISION:
            if not self.comision_id or self.comision_id != mca.comision_id:
                raise ValidationError("La comisión del item no coincide con la de la cursada (MCA).")

        elif self.target_type == self.Target.TITULAR:
            if not self.titular_id or self.titular_id != (mca.titular_id or None):
                raise ValidationError("El TITULAR del item no coincide con el TITULAR de la cursada (MCA).")
            if self.jtp_id is not None:
                raise ValidationError("En un item TITULAR, el campo JTP debe ser nulo.")

        elif self.target_type == self.Target.JTP:
            if not self.jtp_id or self.jtp_id != (mca.jtp_id or None):
                raise ValidationError("El JTP del item no coincide con el JTP de la cursada (MCA).")
            if self.titular_id is not None:
                raise ValidationError("En un item JTP, el campo TITULAR debe ser nulo.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
    
class Nota(models.Model):
    class Estado(models.TextChoices):
        CURSANDO = "CURSANDO", "Cursando"
        PROMOCIONADA = "PROMOCIONADA", "Promocionada"
        APROBADA = "APROBADA", "Aprobada"

    alumno = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="notas")
    mca = models.ForeignKey("academics.MateriaComisionAnio", on_delete=models.CASCADE, related_name="notas")

    # Nota numérica (si no aplica, dejala en null y usás solo 'estado')
    nota = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    estado = models.CharField(max_length=16, choices=Estado.choices)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("alumno", "mca")
        indexes = [
            models.Index(fields=["alumno"]),
            models.Index(fields=["mca"]),
            models.Index(fields=["estado"]),
        ]

    def __str__(self):
        return f"{self.alumno} — {self.mca} [{self.estado}]"

    def clean(self):
        # si querés restringir nota/estado juntos:
        if self.estado == self.Estado.APROBADA and self.nota is None:
            # opcional: exigir nota cuando está aprobada
            pass