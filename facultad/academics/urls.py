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
    path("mca/<int:mca_id>/resena/editar/", views.editar_resena_mca, name="editar_resena_mca"),
    path("mca/<int:mca_id>/resena/eliminar/", views.eliminar_resena_mca, name="eliminar_resena_mca"),
    path("admin-panel/", views.AdminPanelView.as_view(), name="admin_panel"),
    path("admin/departamentos/", views.DepartmentList.as_view(), name="dept_list"),
    path("admin/departamentos/nuevo/", views.DepartmentCreate.as_view(), name="dept_create"),
    path("admin/departamentos/<int:pk>/editar/", views.DepartmentUpdate.as_view(), name="dept_update"),
    path("admin/departamentos/<int:pk>/eliminar/", views.DepartmentDelete.as_view(), name="dept_delete"),
    path("admin/materias/", views.MateriaList.as_view(), name="materia_list"),
    path("admin/materias/nuevo/", views.MateriaCreate.as_view(), name="materia_create"),
    path("admin/materias/<int:pk>/editar/", views.MateriaUpdate.as_view(), name="materia_update"),
    path("admin/materias/<int:pk>/eliminar/", views.MateriaDelete.as_view(), name="materia_delete"),
    path("comisiones/", views.ComisionList.as_view(), name="comision_list"),
    path("comisiones/nueva/", views.ComisionCreateView.as_view(), name="comision_create"),
    path("comisiones/<int:pk>/editar/", views.ComisionUpdateView.as_view(), name="comision_update"),
    path("comisiones/<int:pk>/eliminar/", views.ComisionDelete.as_view(), name="comision_delete"),
]

