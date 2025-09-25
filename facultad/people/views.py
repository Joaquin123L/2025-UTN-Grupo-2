import json
from django.contrib.auth import login, authenticate
from .forms import UserCreationForm
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q, Avg, Count
from people.models import User
from academics.models import MateriaComisionAnio, ResenaItem
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import localtime


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

def _count_text(n: int) -> str:
    if n == 1:
        return "1 opinión"
    if n < 1000:
        return f"{n} opiniones"
    miles = n / 1000.0
    txt = f"{miles:.1f}".replace(".", ",")
    if txt.endswith(",0"):
        txt = txt[:-2]
    return f"{txt} k opiniones"


def perfil_profesor(request, username):
    profesor = get_object_or_404(User, username=username, rol="PRO")

    # Header: materias / comisiones donde figura
    relaciones = (
        MateriaComisionAnio.objects
        .filter(Q(titular=profesor) | Q(jtp=profesor) | Q(ayudante=profesor))
        .select_related("materia", "comision")
        .order_by("materia__nombre", "comision__nombre", "anio")
    )
    materias = (
        relaciones.values_list("materia__id", "materia__nombre")
        .distinct().order_by("materia__nombre")
    )
    comisiones = (
        relaciones.values_list("comision__id", "comision__nombre", "anio")
        .distinct().order_by("comision__nombre", "anio")
    )

    # --------- COMENTARIOS (TITULAR + JTP) ----------
    # Unión explícita de los dos querysets para evitar cualquier ambigüedad.
    qs_tit = ResenaItem.objects.filter(target_type="TITULAR", titular_id=profesor.id)
    qs_jtp = ResenaItem.objects.filter(target_type="JTP", jtp_id=profesor.id)
    items_qs = (qs_tit | qs_jtp).order_by("-created_at")  # mismos campos => union OK

    agg = items_qs.aggregate(promedio=Avg("puntuacion"), cantidad=Count("id"))
    promedio = float(agg["promedio"] or 0.0)
    cantidad = int(agg["cantidad"] or 0)

    full_stars = int(round(promedio)) if cantidad else 0
    if full_stars < 0: full_stars = 0
    if full_stars > 5: full_stars = 5

    rating = {
        "score": f"{promedio:.1f}" if cantidad else "—",
        "count_text": _count_text(cantidad),
        "full_stars": full_stars,
    }

    comentarios = [
        {
            "estrellas": int(it.puntuacion or 0),
            "texto": (it.comentario or "").strip(),
            "fecha": localtime(it.created_at).strftime("%d/%m/%Y %H:%M"),
            # útil si querés mostrar de qué rol vino:
            # "rol": "Titular" if it.target_type == "TITULAR" else "JTP",
        }
        for it in items_qs[:50]
    ]

    # (opcional) para debug interno
    por_rol = {"titular": qs_tit.count(), "jtp": qs_jtp.count()}

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
            "por_rol": por_rol,
        },
    )