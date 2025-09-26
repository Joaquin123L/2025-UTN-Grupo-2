# academics/urls.py
from django.urls import path
from . import views
from .views import perfil_comision

app_name = "academics"
urlpatterns = [
    path("", views.home, name="home"),
    path("materia/<int:materia_id>/", views.perfil_materia, name="perfil_materia"),
    path("materias/<int:materia_id>/comisiones/<int:comision_id>/<int:anio>/", perfil_comision, name="perfil_comision"),
]


