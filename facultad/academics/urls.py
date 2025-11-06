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
    path("admin-panel/", views.AdminPanelView.as_view(), name="admin_panel"),
    path("admin/departamentos/", views.dept_list, name="dept_list"),
    path("admin/departamentos/nuevo/", views.dept_create, name="dept_create"),
    path("admin/departamentos/<int:pk>/editar/", views.dept_update, name="dept_update"),
    path("admin/departamentos/<int:pk>/eliminar/", views.dept_delete, name="dept_delete"),
    path("admin/materias/", views.materia_list, name="materia_list"),
    path("admin/materias/nuevo/", views.materia_create, name="materia_create"),
    path("admin/materias/<int:pk>/editar/", views.materia_update, name="materia_update"),
    path("admin/materias/<int:pk>/eliminar/", views.materia_delete, name="materia_delete"),
    path("admin/comisiones/", views.comision_list, name="comision_list"),
    path("admin/comisiones/nueva/", views.comision_create, name="comision_create"),
    path("admin/comisiones/<int:pk>/editar/", views.comision_update, name="comision_update"),
    path("admin/comisiones/<int:pk>/eliminar/", views.comision_delete, name="comision_delete"),
]


