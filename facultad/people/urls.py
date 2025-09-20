from django.urls import path
from django.contrib.auth import views as auth_views
from . import views


app_name = "people"

urlpatterns = [
    path(
        "login/", views.login_view, name="login",
    ),
    path("register/", views.register, name="register"),
    path("olvide-clave/", views.olvideClave, name="olvideClave"),
    path("alta-profesor/", views.altaProfesor, name="altaProfesor"),
]
