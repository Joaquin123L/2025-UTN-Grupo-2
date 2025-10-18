import json
from better_profanity import profanity
from django.contrib.auth import login, authenticate
from django.urls import reverse_lazy
from .forms import SignupForm, UserCreationForm
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q, Avg, Count
from people.models import User
from academics.models import MateriaComisionAnio, ResenaItem, Resena, Nota, Materia
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import localtime
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
import unicodedata
from collections import Counter
from django.conf import settings
from academics.plan_loader import load_plan_rows
from better_profanity import profanity

from django.views import View
from django.urls import NoReverseMatch 
from allauth.account.views import SignupView
from django.contrib.auth import logout

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

        if user is not None:
            login(request, user)
            return redirect("academics:home")
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


def _norm(s: str) -> str:
    """Normaliza para comparar: minúsculas, sin tildes, solo alfanum y espacios simples."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in s.lower())
    s = " ".join(s.split())
    return s

def _get_user_carrera(user) -> str | None:
    """
    Intenta leer la carrera desde varios atributos/relaciones comunes.
    Devuelve el string tal cual (sin normalizar) si lo encuentra, o None.
    """
    # 1) Atributos directos frecuentes
    direct_attrs = ("carrera", "career", "major", "programa", "plan_carrera", "plan", "titulo")
    for a in direct_attrs:
        val = getattr(user, a, None)
        if isinstance(val, str) and val.strip():
            return val.strip()
        # si es un objeto con 'nombre'/'name'
        if hasattr(val, "nombre"):
            return str(val.nombre).strip()
        if hasattr(val, "name"):
            return str(val.name).strip()

    # 2) Relaciones típicas de perfil
    rels = ("perfil", "profile", "userprofile", "studentprofile", "alumno", "estudiante")
    for rel in rels:
        obj = getattr(user, rel, None)
        if obj:
            for a in direct_attrs:
                val = getattr(obj, a, None)
                if isinstance(val, str) and val.strip():
                    return val.strip()
                if hasattr(val, "nombre"):
                    return str(val.nombre).strip()
                if hasattr(val, "name"):
                    return str(val.name).strip()

    return None

def _pick_carrera_for_user(plan_rows: list[dict], user) -> tuple[str | None, list[dict]]:
    """
    Elige la carrera adecuada para el usuario comparando su string con las
    carreras presentes en el plan. Devuelve (carrera_elegida, plan_filtrado).
    """
    if not plan_rows:
        return (None, [])

    # carreras disponibles en archivo
    carreras = sorted({r["carrera"] for r in plan_rows if r.get("carrera")})
    if not carreras:
        return (None, plan_rows)

    # 1) user -> string candidata
    user_raw = _get_user_carrera(user)
    user_norm = _norm(user_raw or "")

    # 2) si no hay nada en el usuario, usar settings ó la más frecuente
    if not user_norm:
        default_c = getattr(settings, "ACADEMICS_PLAN_DEFAULT_CARRERA", None)
        if default_c:
            chosen = default_c
        else:
            chosen = Counter(r["carrera"] for r in plan_rows).most_common(1)[0][0]
        return (chosen, [r for r in plan_rows if r["carrera"] == chosen])

    # 3) Fuzzy: elegimos la carrera cuyo _norm() más se “contiene”/parece
    def score(target: str) -> int:
        t = _norm(target)
        # heurística simple: tokens en común + contains
        tokens_u = set(user_norm.split())
        tokens_t = set(t.split())
        inter = len(tokens_u & tokens_t)
        contains = 1 if (user_norm in t or t in user_norm) else 0
        return inter * 10 + contains  # pondero fuerte tokens

    best = max(carreras, key=score)
    # si la mejor coincidencia tiene score 0, caemos al default / más frecuente
    if score(best) == 0:
        default_c = getattr(settings, "ACADEMICS_PLAN_DEFAULT_CARRERA", None)
        chosen = default_c or Counter(r["carrera"] for r in plan_rows).most_common(1)[0][0]
    else:
        chosen = best

    return (chosen, [r for r in plan_rows if r["carrera"] == chosen])

class PerfilUsuarioView(LoginRequiredMixin, TemplateView):
    template_name = "people/perfil_usuario.html"
    login_url = "people:login"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u = self.request.user

        # Promedio (igual que tenías)
        promedio = (
            Nota.objects.filter(alumno=u, nota__isnull=False)
            .aggregate(val=Avg("nota"))["val"]
        )

        # Distribución por estado (sobre Notas existentes)
        rows = Nota.objects.filter(alumno=u).values("estado").annotate(c=Count("id"))
        tot_notas = sum(r["c"] for r in rows) or 0
        pct_estados = {r["estado"]: round(100 * r["c"] / (tot_notas or 1), 2) for r in rows}
        count_by_estado = {r["estado"]: r["c"] for r in rows}

        # === Donut: usar carrera del usuario para filtrar el plan ===
        all_plan = list(load_plan_rows())  # lee plan.json/csv
        carrera_elegida, plan = _pick_carrera_for_user(all_plan, u)
        total_plan = len(plan)

        # Materias con alguna nota del usuario (distinct por materia)
        cursadas_ids = set(
            Nota.objects.filter(alumno=u)
            .values_list("mca__materia_id", flat=True)
            .distinct()
        )

        # nombre -> id (si no existe en BD, la materia igual cuenta como pendiente)
        by_name = {m.nombre.lower(): m.id for m in Materia.objects.only("id", "nombre")}
        tocadas_en_plan = 0
        for r in plan:
            mid = by_name.get(r["materia"].lower())
            if mid and mid in cursadas_ids:
                tocadas_en_plan += 1
        pendientes_count = max(total_plan - tocadas_en_plan, 0)

        # Contadores de estados ya cursados
        cursando_count = count_by_estado.get(Nota.Estado.CURSANDO, 0)
        promo_count    = count_by_estado.get(Nota.Estado.PROMOCIONADA, 0)
        apro_count     = count_by_estado.get(Nota.Estado.APROBADA, 0)

        donut_counts = {
            "Cursando": cursando_count,
            "Promocionada": promo_count,
            "Aprobada": apro_count,
            "Pendientes": pendientes_count if total_plan else 0,
        }
        donut_total = sum(donut_counts.values()) or 1
        donut_pct = {k: round(v * 100 / donut_total, 2) for k, v in donut_counts.items()}

        # === Lo tuyo de “evaluar materias” + comentarios (sin cambios funcionales)
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
            "pct": pct_estados,
            "mcas_para_evaluar": mcas_para_evaluar,
            "comentarios_todos": comentarios_todos,
            "comentarios_total": len(comentarios_todos),
            "orden": orden,

            # donut
            "donut_counts": donut_counts,
            "donut_pct": donut_pct,
            "donut_total": donut_total,
            "dashboard_carrera": carrera_elegida or "Plan",
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