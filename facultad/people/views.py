import json
from better_profanity import profanity
from django.contrib.auth import login, authenticate
from django.urls import reverse_lazy
from .forms import SignupForm, UserCreationForm
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q, Avg, Count
from people.models import User
from academics.models import MateriaComisionAnio, ResenaItem, Resena, Nota
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import localtime
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.views import View
from django.urls import NoReverseMatch 
from allauth.account.views import SignupView
from django.contrib.auth import logout
from django.urls import reverse_lazy
from django.views.generic import  CreateView, UpdateView, DeleteView
from .models import User as UserModel
from .forms import ProfessorCreateForm, ProfessorUpdateForm



User = get_user_model()

class CustomSignupView(SignupView):
    template_name = 'people/register.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            logout(request)
        return super().dispatch(request, *args, **kwargs)
    

register = CustomSignupView.as_view()

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

        if user is not None and user.rol in [User.Role.ALUMNO]:
            login(request, user)
            return redirect("academics:home")
        elif user is not None and user.rol in [User.Role.ADMIN]:
            login(request, user)
            return redirect("academics:admin_panel")
        else:
            messages.error(request, "Email o contraseña incorrectos.")

    return render(request, "people/login.html")


def olvideClave(request):
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
        first_name = (data.get("first_name") or "").strip() or None
        last_name = (data.get("last_name") or "").strip() or None
        imagen_perfil = data.get("imagen_perfil") or None

        if email and legajo:
            user = User(username=email, email=email, rol=User.Role.PROFESOR, legajo=legajo, first_name=first_name, last_name=last_name, imagen_perfil=imagen_perfil)
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

    seen = set()
    comisiones = []
    for r in relaciones:
        key = (r.materia_id, r.comision_id, r.anio)
        if key in seen:
            continue
        seen.add(key)
        comisiones.append({
            "materia_id": r.materia_id,
            "id": r.comision_id,
            "nombre": r.comision.nombre,
            "anio": r.anio,
        })
    comisiones.sort(key=lambda x: (x["nombre"], x["anio"]))

    qs_tit = ResenaItem.objects.filter(target_type="TITULAR", titular_id=profesor.id)
    qs_jtp = ResenaItem.objects.filter(target_type="JTP", jtp_id=profesor.id)

    order = request.GET.get("order", "desc")
    if order not in ("asc", "desc"):
        order = "desc"
    order_prefix = "" if order == "asc" else "-"

    items_qs = (qs_tit | qs_jtp).order_by(f"{order_prefix}created_at")

    agg = items_qs.aggregate(promedio=Avg("puntuacion"), cantidad=Count("id"))
    promedio = float(agg["promedio"] or 0.0)
    cantidad = int(agg["cantidad"] or 0)
    full_stars = max(0, min(5, int(round(promedio)) if cantidad else 0))

    rating = {
        "score": f"{promedio:.1f}" if cantidad else "—",
        "count_text": _count_text(cantidad),
        "full_stars": full_stars,
    }

    comentarios = [
        {
            "estrellas": int(it.puntuacion or 0),
            "texto": profanity.censor((it.comentario or "").strip()),
            "fecha": localtime(it.created_at).strftime("%d/%m/%Y %H:%M"),
        }
        for it in items_qs[:50]
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
            "order": order,
        },
    )

class PerfilUsuarioView(LoginRequiredMixin, TemplateView):
    template_name = "people/perfil_usuario.html"
    login_url = "people:login"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u = self.request.user

        promedio = (
            Nota.objects.filter(alumno=u, nota__isnull=False)
            .aggregate(val=Avg("nota"))["val"]
        )

        rows = Nota.objects.filter(alumno=u).values("estado").annotate(c=Count("id"))
        tot = sum(r["c"] for r in rows) or 1
        pct = {r["estado"]: round(100 * r["c"] / tot, 2) for r in rows}

        mcas_para_evaluar = (
            MateriaComisionAnio.objects
            .filter(
                notas__alumno=u,
                notas__estado__in=[Nota.Estado.APROBADA, Nota.Estado.PROMOCIONADA],
            )
            .exclude(resenas__alumno=u)
            .select_related("materia", "comision")
            .order_by("materia__nombre", "comision__nombre", "-anio")
            .distinct()
        )

        orden = self.request.GET.get("orden", "desc")
        if orden not in ("asc", "desc"):
            orden = "desc"
        order_by = ("-" if orden == "desc" else "") + "resena__created_at"


        base_qs = (
            ResenaItem.objects
            .filter(resena__alumno=u)
            .select_related(
                "resena", "resena__mca",
                "resena__mca__materia", "resena__mca__comision",
                "materia", "comision", "titular", "jtp",
            )
            .order_by(order_by, "id")  
        )

        comentarios_todos = []
        for it in base_qs:
            mca = it.resena.mca

            if it.target_type == ResenaItem.Target.MATERIA:
                comentarios_todos.append({
                    "tipo": "Materia",
                    "badge": "materia",
                    "title": mca.materia.nombre,
                    "subtitle": f"Año {mca.anio}",
                    "fecha": it.resena.created_at,
                    "puntuacion": it.puntuacion,
                    "comentario": profanity.censor((it.comentario or "").strip()),
                })

            elif it.target_type == ResenaItem.Target.COMISION:
                com = mca.comision.nombre if mca.comision else "—"
                comentarios_todos.append({
                    "tipo": "Comisión",
                    "badge": "comision",
                    "title": f"{mca.materia.nombre} — {com}",
                    "subtitle": f"Año {mca.anio}",
                    "fecha": it.resena.created_at,
                    "puntuacion": it.puntuacion,
                    "comentario": profanity.censor((it.comentario or "").strip()),
                })

            elif it.target_type in (ResenaItem.Target.TITULAR, ResenaItem.Target.JTP):
                rol = "Titular" if it.target_type == ResenaItem.Target.TITULAR else "JTP"
                prof = (it.titular or it.jtp)
                nombre = (prof.get_full_name() or prof.username) if prof else "—"
                com = mca.comision.nombre if mca.comision else "—"
                comentarios_todos.append({
                    "tipo": f"Profesor · {rol}",
                    "badge": "profesor",
                    "title": nombre,
                    "subtitle": f"{mca.materia.nombre} — {com} · Año {mca.anio}",
                    "fecha": it.resena.created_at,
                    "puntuacion": it.puntuacion,
                    "comentario": profanity.censor((it.comentario or "").strip()),
                })

        ctx.update({
            "promedio": promedio,
            "pct": pct,
            "mcas_para_evaluar": mcas_para_evaluar,
            "comentarios_todos": comentarios_todos,
            "comentarios_total": len(comentarios_todos),
            "orden": orden,
        })
        return ctx
    
class SubirAvatarView(LoginRequiredMixin, View):
    login_url = "people:login"

    def _go_back(self):
        try:
            return redirect("people:perfil")
        except NoReverseMatch:
            return redirect("/people/perfil/")

    def post(self, request):
        file = request.FILES.get("imagen")
        if not file:
            messages.error(request, "No seleccionaste ninguna imagen.")
            return self._go_back()

        ok_types = {"image/jpeg", "image/png", "image/webp"}
        if file.content_type not in ok_types:
            messages.error(request, "Formato no soportado. Usa JPG, PNG o WebP.")
            return self._go_back()

        if file.size > 5 * 1024 * 1024:
            messages.error(request, "La imagen supera 5 MB.")
            return self._go_back()

        u = request.user
        u.imagen_perfil = file
        u.save(update_fields=["imagen_perfil"])

        messages.success(request, "¡Tu foto de perfil fue actualizada!")
        return self._go_back() 


def professor_list(request):
    profesores = (
        UserModel.objects
        .filter(rol=UserModel.Role.PROFESOR)
        .order_by("last_name", "first_name")
    )
    return render(request, "people/professor_list.html", {"object_list": profesores})


def professor_form(request, pk=None):
    instance = None
    if pk:
        instance = get_object_or_404(UserModel, pk=pk, rol=UserModel.Role.PROFESOR)

    FormCls = ProfessorUpdateForm if instance else ProfessorCreateForm

    if request.method == "POST":
        form = FormCls(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Profesor guardado correctamente.")
            return redirect("people:professor_list")
        # si no es válido, sigue al render con errores
    else:
        form = FormCls(instance=instance)

    return render(
        request,
        "people/professor_form.html",
        {"form": form, "professor": instance},
    )
class ProfessorDeleteView(LoginRequiredMixin, DeleteView):
    model = UserModel
    template_name = "people/professor_confirm_delete.html"
    success_url = reverse_lazy("people:professor_list")
    login_url = "people:login"

    def get_queryset(self):
        # solo permite borrar PROFESORES
        qs = super().get_queryset()
        if hasattr(UserModel, "Role"):
            qs = qs.filter(rol=UserModel.Role.PROFESOR)
        return qs