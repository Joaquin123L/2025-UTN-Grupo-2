from django.urls import path
from . import views

app_name = "academics"
urlpatterns = [
    path("", views.DepartmentListView.as_view(), name="home"),
    path("subjects/<int:department_id>/", views.MateriasListView.as_view(), name="subjects_by_dept"),
    path("materia/<int:materia_id>/", views.perfil_materia, name="perfil_materia"),
    path("materias/<int:materia_id>/comisiones/<int:comision_id>/<int:anio>/", views.perfil_comision, name="perfil_comision"),
    path("materias/<int:materia_id>/<int:anio>/comisiones/", views.MateriaComisionAnioListView.as_view(), name="materia_comisiones"),
    path("evaluar/<int:mca_id>/", views.evaluar_mca, name="evaluar_mca"),
]


