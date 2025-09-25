import json
from django.contrib.auth import login, authenticate
from .forms import UserCreationForm
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from people.models import User
from academics.models import MateriaComisionAnio
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt

User = get_user_model()

def register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data["email"]
            user.rol = User.Role.ALUMNO
            user.legajo = request.POST.get("legajo") or None
            user.save()
            login(request, user)
            return redirect("people:login")
    else:
        form = UserCreationForm()
    return render(request, "people/register.html", {"form": form})

def login_view(request):
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""

        user = None
        user = authenticate(request, username=email, password=password)
        if user is None:
            try:
                u = User.objects.get(email=email)
                user = authenticate(request, username=u.get_username(), password=password)
            except User.DoesNotExist:
                user = None

        if user is not None:
            login(request, user)
            return redirect("academics:home")
        else:
            messages.error(request, "Email o contraseña incorrectos.")

    return render(request, "people/login.html")


def olvideClave(request):
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        return redirect("people:login")
    return render(request, "people/olvide-clave.html")

@csrf_exempt
def altaProfesor(request):
    if request.method == "POST":
        if request.content_type and "application/json" in request.content_type:
            try:
                data = json.loads(request.body or "{}")
            except json.JSONDecodeError:
                data = {}
        else:
            data = request.POST
        email = (data.get("email") or "").strip().lower()
        legajo = (data.get("legajo") or "").strip() or None

        if email and legajo:
            user = User(username=email, email=email, rol=User.Role.PROFESOR, legajo=legajo)
            user.set_unusable_password()
            user.save()
            messages.success(request, "Profesor dado de alta correctamente.")
            return redirect("people:login")
        else:
            messages.error(request, "Email y legajo son obligatorios.")
    return render(request, "people/login.html")

def perfil_profesor(request, username):
    profesor = get_object_or_404(User, username=username, rol="PRO")

    relaciones = (
        MateriaComisionAnio.objects
        .filter(Q(titular=profesor) | Q(jtp=profesor) | Q(ayudante=profesor))
        .select_related("materia", "comision")
        .order_by("materia__nombre", "comision__nombre", "anio")
    )

    materias = (
        relaciones.values_list("materia__id", "materia__nombre")
        .distinct()
        .order_by("materia__nombre")
    )
    comisiones = (
        relaciones.values_list("comision__id", "comision__nombre", "anio")
        .distinct()
        .order_by("comision__nombre", "anio")
    )

    rating = {"score": 4.3, "count_text": "1,2 k opiniones"}

    comentarios = [
        {"estrellas": 4, "texto": "Da la materia para el orto, dice una cosa y hace otra, yo la tuve en am2", "fecha": "14/08/2025"},
        {"estrellas": 4, "texto": "Da la materia para el orto, dice una cosa y hace otra, yo la tuve en am2", "fecha": "14/08/2025"},
        {"estrellas": 4, "texto": "Da la materia para el orto, dice una cosa y hace otra, yo la tuve en am2", "fecha": "14/08/2025"},
        {"estrellas": 4, "texto": "Da la materia para el orto, dice una cosa y hace otra, yo la tuve en am2", "fecha": "14/08/2025"},
        {"estrellas": 4, "texto": "Da la materia para el orto, dice una cosa y hace otra, yo la tuve en am2", "fecha": "14/08/2025"},
        {"estrellas": 4, "texto": "Da la materia para el orto, dice una cosa y hace otra, yo la tuve en am2", "fecha": "14/08/2025"},
        {"estrellas": 4, "texto": "Da la materia para el orto, dice una cosa y hace otra, yo la tuve en am2", "fecha": "14/08/2025"},
        {"estrellas": 4, "texto": "Da la materia para el orto, dice una cosa y hace otra, yo la tuve en am2", "fecha": "14/08/2025"},
    ]

    return render(
        request,
        "people/perfil_profesor.html",
        {
            "profesor": profesor,
            "relaciones": relaciones,
            "materias": materias,
            "comisiones": comisiones,
            "rating": rating,
            "comentarios": comentarios,
        },
    )