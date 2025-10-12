# people/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    class Role(models.TextChoices):
        ALUMNO = "ALU", "Alumno"
        PROFESOR = "PRO", "Profesor"

    rol = models.CharField(max_length=3, choices=Role.choices)
    legajo = models.CharField(max_length=20, unique=True, null=True, blank=True)  # solo alumnos
    username = models.CharField(max_length=150, blank=True, default='')

    imagen_perfil = models.ImageField(
        upload_to="profiles/", null=True, blank=True
    )
