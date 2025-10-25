from django.urls import path
from django.contrib.auth import views as auth_views
from allauth.account.views import SignupView
from . import views
from .views import PerfilUsuarioView


app_name = "people"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("register/", views.register, name="account_signup"),
    path("register/", views.register, name="register"),
    path("olvide-clave/", views.olvideClave, name="olvideClave"),
    path("alta-profesor/", views.altaProfesor, name="altaProfesor"),
    path("perfil/", PerfilUsuarioView.as_view(), name="perfil"),
    path("perfil/upload-avatar/", views.SubirAvatarView.as_view(), name="upload_avatar"),
    path("profesores/", views.professor_list, name="professor_list"),
    path("profesor/nuevo/", views.professor_form, name="professor_form"),
    path("profesor/<int:pk>/editar/", views.professor_form, name="professor_form"),
    path("profesor/<int:pk>/eliminar/", views.ProfessorDeleteView.as_view(), name="confirm_delete"),
    path("profesor/<str:username>/", views.perfil_profesor, name="perfil_profesor"),
    
    
]
