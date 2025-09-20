# academics/urls.py
from django.urls import path
from . import views

app_name = "academics"
urlpatterns = [
    path("", views.home, name="home"),
]
