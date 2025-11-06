from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Max, Value, OuterRef, Subquery, IntegerField, FloatField, Exists, Q
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, render, redirect
from django.utils.timezone import localtime
from django.utils import timezone
from academics.models import MateriaComisionAnio, ResenaItem, Materia, Department, Nota, Resena, Comision, CensoredWord
from .admin import CensoredWordAdmin
from people.models import User
from django.contrib import messages
from django.db import transaction, IntegrityError
from django.db.models.deletion import ProtectedError
from django.http import HttpResponseForbidden, JsonResponse, Http404
from academics.models import Department
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView
from better_profanity import profanity
from academics.mixins import AdminRequiredMixin
import json
from django.urls import reverse, reverse_lazy
import json
from django.utils.safestring import mark_safe
from django.contrib.auth import get_user_model

User = get_user_model()

class DepartmentListView(LoginRequiredMixin, ListView):
    template_name = "academics/home.html"
    context_object_name = "departments"
    model = Department

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # ---- TOP MATERIAS (promedio, y desempate por cantidad) ----
        top_materias = (
            Materia.objects
            .annotate(
                promedio=Avg(
                    "resenas_items__puntuacion",
                    filter=Q(resenas_items__target_type="MATERIA")
                ),
                cantidad=Count(
                    "resenas_items",
                    filter=Q(resenas_items__target_type="MATERIA")
                )
            )
            .filter(cantidad__gt=0)
            .order_by("-promedio", "-cantidad", "nombre")[:10]
        )

        # ---- TOP PROFES (TITULAR + JTP unificados) ----
        items_prof = (
            ResenaItem.objects
            .filter(target_type__in=["TITULAR", "JTP"])
            .annotate(prof_id=Coalesce("titular_id", "jtp_id"))
        )

        profesores_agregados = (
            items_prof.values("prof_id")
            .annotate(
                promedio=Avg("puntuacion"),
                cantidad=Count("id"),
            )
            .order_by("-promedio", "-cantidad", "prof_id")[:10]
        )

        users = {
            u.id: u for u in User.objects.filter(
                id__in=[r["prof_id"] for r in profesores_agregados]
            )
        }
        top_profes = [
            {"user": users[r["prof_id"]], "promedio": r["promedio"], "cantidad": r["cantidad"]}
            for r in profesores_agregados
            if users.get(r["prof_id"])
        ]

        ctx["top_materias"] = top_materias
        ctx["top_profes"] = top_profes
        return ctx

class MateriasListView(LoginRequiredMixin, ListView):
    template_name = "academics/materias.html"
    context_object_name = "subjects"
    model = Materia

    def get_queryset(self):
        self.department = get_object_or_404(Department, pk=self.kwargs["department_id"])

        # Subqueries para evitar depender del related_name
        avg_sq = (ResenaItem.objects
                  .filter(target_type="MATERIA", materia_id=OuterRef('pk'))
                  .values('materia_id')
                  .annotate(avg=Avg('puntuacion'))
                  .values('avg')[:1])

        cnt_sq = (ResenaItem.objects
                  .filter(target_type="MATERIA", materia_id=OuterRef('pk'))
                  .values('materia_id')
                  .annotate(cnt=Count('id'))
                  .values('cnt')[:1])

        return (Materia.objects
                .filter(departamento_id=self.department.pk, eliminado=False)
                .select_related("departamento")
                .annotate(
                    avg_rating=Coalesce(Subquery(avg_sq, output_field=FloatField()), Value(0.0)),
                    opiniones_cnt=Coalesce(Subquery(cnt_sq, output_field=IntegerField()), Value(0)),
                )
                .order_by("nombre"))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["department"] = self.department
        ctx["current_year"] = timezone.now().year

        # Construyo el objeto rating que espera card.html para cada materia
        for d in ctx["subjects"]:
            promedio = float(getattr(d, "avg_rating", 0.0) or 0.0)
            cantidad = int(getattr(d, "opiniones_cnt", 0) or 0)
            full_stars = max(0, min(5, int(round(promedio)))) if cantidad else 0
            d.rating = {
                "score": f"{promedio:.1f}" if cantidad else "—",
                "count_text": _count_text(cantidad),
                "full_stars": full_stars,
            }
        return ctx

class MateriaComisionAnioListView(LoginRequiredMixin, ListView):
    template_name = "academics/comision.html"
    context_object_name = "mca_list"
    model = MateriaComisionAnio


    def get_queryset(self):
        self.materia = get_object_or_404(Materia, pk=self.kwargs["materia_id"], eliminado=False)
        self.anio = int(self.kwargs.get("anio") or timezone.now().year)
        return (MateriaComisionAnio.objects
                .filter(materia_id=self.materia.pk, anio=self.anio)
                .select_related("comision", "titular", "jtp")
                .order_by("comision__nombre"))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        system_year = timezone.now().year

        ctx["materia"] = self.materia
        ctx["current_year"] = self.anio
        ctx["year_choices"] = [system_year - i for i in range(6)]

        # —— ratings por cada MCA del queryset ——
        mca_with_rating = []
        for mca in ctx["mca_list"]:
            agg = (
                ResenaItem.objects
                .filter(
                    target_type="COMISION",
                    resena__mca=mca,
                    comision_id=mca.comision_id,
                )
                .aggregate(
                    promedio=Coalesce(Avg("puntuacion"), Value(0.0)),
                    cantidad=Coalesce(Count("id"), Value(0)),
                )
            )
            promedio = float(agg["promedio"])
            cantidad = int(agg["cantidad"])
            full_stars = max(0, min(5, int(round(promedio)))) if cantidad else 0

            rating = {
                "score": f"{promedio:.1f}" if cantidad else "—",
                "count_text": _count_text(cantidad),
                "full_stars": full_stars,
            }
            mca_with_rating.append((mca, rating))

        ctx["mca_with_rating"] = mca_with_rating
        return ctx

def _count_text(n: int) -> str:
        # usa tu implementación; dejo un fallback simple
        return f"{n} opiniones" if n < 1000 else f"{n/1000:.1f} k opiniones"

def perfil_comision(request, materia_id: int, comision_id: int, anio: int):
    mca = get_object_or_404(
        MateriaComisionAnio,
        materia_id=materia_id,
        comision_id=comision_id,
        anio=anio,
    )
    materia = mca.materia
    comision = mca.comision

    # --- NUEVO: orden por query param ---
    order = (request.GET.get("order") or "desc").lower()
    if order not in {"asc", "desc"}:
        order = "desc"

    base_qs = (
        ResenaItem.objects
        .filter(target_type="COMISION", resena__mca=mca, comision_id=comision_id)
    )

    # Agregados (independientes del orden)
    agg = base_qs.aggregate(promedio=Avg("puntuacion"), cantidad=Count("id"))
    promedio = float(agg["promedio"] or 0.0)
    cantidad = int(agg["cantidad"] or 0)
    full_stars = int(round(promedio)) if cantidad else 0
    full_stars = max(0, min(5, full_stars))
    rating = {
        "score": f"{promedio:.1f}" if cantidad else "—",
        "count_text": _count_text(cantidad),
        "full_stars": full_stars,
    }

    # Orden aplicado a los items
    order_by = "created_at" if order == "asc" else "-created_at"
    items_qs = base_qs.order_by(order_by)

    comentarios = [
        {
            "estrellas": int(it.puntuacion or 0),
            "texto": profanity.censor((it.comentario or "").strip()),
            "fecha": localtime(it.created_at).strftime("%d/%m/%Y"),
        }
        for it in items_qs[:50]
    ]

    return render(
        request,
        "academics/perfil_comision.html",
        {
            "materia": materia,
            "comision": comision,
            "anio": anio,
            "titular": mca.titular,
            "jtp": mca.jtp,
            "rating": rating,
            "comentarios": comentarios,
            "order": order,  # <- pasar al template para marcar el seleccionado
        },
    )

def perfil_materia(request, materia_id: int):
    materia = get_object_or_404(Materia, id=materia_id)

    mcas = (
        MateriaComisionAnio.objects
        .filter(materia_id=materia_id)
        .select_related("comision", "titular", "jtp")
        .order_by("-anio", "comision__nombre")
    )

    profes, seen = [], set()
    for m in mcas:
        for prof in (m.titular, m.jtp):
            if prof and prof.username not in seen:
                profes.append(prof)
                seen.add(prof.username)

    comisiones_qs = (
        mcas.values("comision__id", "comision__nombre")
            .annotate(max_anio=Max("anio"))
            .order_by("comision__nombre")
    )
    comisiones = [
        {"id": row["comision__id"], "nombre": row["comision__nombre"], "anio": row["max_anio"]}
        for row in comisiones_qs
    ]

    order = request.GET.get("order", "desc")
    if order not in ("asc", "desc"):
        order = "desc"
    order_prefix = "" if order == "asc" else "-"

    items_qs = (
        ResenaItem.objects
        .filter(target_type="MATERIA", resena__mca__materia_id=materia_id)
        .order_by(f"{order_prefix}created_at")
    )

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
            "fecha": localtime(it.created_at).strftime("%d/%m/%Y"),
        }
        for it in items_qs[:50]
    ]

    return render(
        request,
        "academics/perfil_materia.html",
        {
            "materia": materia,
            "profes": profes,
            "comisiones": comisiones,
            "rating": rating,
            "comentarios": comentarios,
            "order": order,
        },
    )

@login_required
def evaluar_mca(request, mca_id):
    u = request.user
    mca = get_object_or_404(
        MateriaComisionAnio.objects.select_related("materia", "comision", "titular", "jtp"),
        pk=mca_id
    )

    # ===== VALIDACIONES DE ACCESO (GET y POST) =====
    tiene_nota_valida = Nota.objects.filter(
        alumno=u,
        mca=mca,
        estado__in=[Nota.Estado.APROBADA, Nota.Estado.PROMOCIONADA],
    ).exists()

    ya_tiene_resena = Resena.objects.filter(alumno=u, mca=mca).exists()

    if not tiene_nota_valida:
        messages.error(request, "Solo podés evaluar materias que aprobaste o promocionaste.")
        return redirect('people:perfil')

    if ya_tiene_resena:
        messages.info(request, "Ya enviaste una reseña para esta cursada.")
        return redirect('people:perfil')

    # ===== GET: mostrar formulario =====
    if request.method == "GET":
        ctx = {
            "mca": mca,
            "titular": mca.titular,
            "jtp": mca.jtp,
        }
        return render(request, "academics/evaluar_mca.html", ctx)

    # ===== POST: re-validar y crear reseña + items =====
    # Revalido nuevamente por si hubo carrera entre GET y POST
    if Resena.objects.filter(alumno=u, mca=mca).exists():
        messages.info(request, "Ya enviaste una reseña para esta cursada.")
        return redirect('people:perfil')


    if not Nota.objects.filter(
        alumno=u, mca=mca,
        estado__in=[Nota.Estado.APROBADA, Nota.Estado.PROMOCIONADA]
    ).exists():
        # Alguien manipuló el form o cambió la nota en el medio
        messages.error(request, "Tu estado en la materia ya no habilita enviar reseña.")
        return redirect('people:perfil')

    # Helpers
    def _clean_score(name):
        v = request.POST.get(name)
        if not v:
            return None
        try:
            iv = int(v)
            return iv if 1 <= iv <= 5 else None
        except ValueError:
            return None

    materia_score  = _clean_score("materia_score")
    materia_comment = (request.POST.get("materia_comment") or "").strip()

    comision_score = _clean_score("comision_score")
    comision_comment = (request.POST.get("comision_comment") or "").strip()

    titular_score = _clean_score("titular_score") if mca.titular_id else None
    titular_comment = (request.POST.get("titular_comment") or "").strip() if mca.titular_id else ""

    jtp_score = _clean_score("jtp_score") if mca.jtp_id else None
    jtp_comment = (request.POST.get("jtp_comment") or "").strip() if mca.jtp_id else ""

    if not any([materia_score, comision_score, titular_score, jtp_score]):
        messages.error(request, "Elegí al menos una puntuación antes de enviar.")
        return redirect("academics:evaluar_mca", mca_id=mca.id)

    try:
        with transaction.atomic():
            # Esta línea puede lanzar IntegrityError si alguien duplica el envío:
            resena = Resena.objects.create(alumno=u, mca=mca)

            if materia_score:
                ResenaItem.objects.create(
                    resena=resena,
                    target_type=ResenaItem.Target.MATERIA,
                    puntuacion=materia_score,
                    comentario=materia_comment,
                    materia=mca.materia,
                )

            if comision_score:
                ResenaItem.objects.create(
                    resena=resena,
                    target_type=ResenaItem.Target.COMISION,
                    puntuacion=comision_score,
                    comentario=comision_comment,
                    comision=mca.comision,
                )

            if mca.titular_id and titular_score:
                ResenaItem.objects.create(
                    resena=resena,
                    target_type=ResenaItem.Target.TITULAR,
                    puntuacion=titular_score,
                    comentario=titular_comment,
                    titular=mca.titular,
                )

            if mca.jtp_id and jtp_score:
                ResenaItem.objects.create(
                    resena=resena,
                    target_type=ResenaItem.Target.JTP,
                    puntuacion=jtp_score,
                    comentario=jtp_comment,
                    jtp=mca.jtp,
                )

    except IntegrityError:
        # Respaldo por la UniqueConstraint uq_resena_alumno_mca
        messages.info(request, "Ya existe una reseña para esta cursada.")
        return redirect('people:perfil')


    messages.success(request, "¡Gracias! Tu evaluación fue registrada.")
    return redirect('people:perfil')

# VISTAS ADMIN 
class AdminPanelView(TemplateView):
    """Panel con accesos a los ABM."""
    template_name = "academics/admin_panel.html"

# -------- Departamento ------
@login_required
def dept_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = Department.objects.all().order_by("nombre")
    if q:
        qs = qs.filter(nombre__icontains=q)

    return render(request, "academics/department_list.html", {
        "departments": qs,
        "q": q,
        "create_url": "academics:dept_create",
        "update_name": "academics:dept_update",
        "delete_name": "academics:dept_delete",
    })

@login_required
def dept_create(request):
    if request.method == "GET":
        return render(request, "academics/department_form.html")

    nombre = (request.POST.get("nombre") or "").strip()
    icono = (request.POST.get("icono") or "").strip()
    imagen = request.FILES.get("imagen")  # opcional

    if not nombre:
        messages.error(request, "El nombre es obligatorio.")
        return render(request, "academics/department_form.html", {"nombre": nombre, "icono": icono})

    try:
        d = Department(nombre=nombre, icono=icono)
        if imagen:
            d.imagen = imagen
        d.save()
        messages.success(request, "Se creó correctamente.")
        return redirect("academics:dept_list")
    except IntegrityError:
        messages.error(request, "Ya existe un departamento con ese nombre.")
        return render(request, "academics/department_form.html", {"nombre": nombre, "icono": icono})

@login_required
def dept_update(request, pk: int):
    d = get_object_or_404(Department, pk=pk)

    if request.method == "GET":
        return render(request, "academics/department_form.html", {
            "obj": d, "nombre": d.nombre, "icono": d.icono
        })

    nombre = (request.POST.get("nombre") or "").strip()
    icono = (request.POST.get("icono") or "").strip()
    imagen = request.FILES.get("imagen")

    if not nombre:
        messages.error(request, "El nombre es obligatorio.")
        return render(request, "academics/department_form.html", {"obj": d, "nombre": nombre, "icono": icono})

    d.nombre = nombre
    d.icono = icono
    if imagen:
        d.imagen = imagen

    try:
        d.save()
        messages.success(request, "Se actualizó correctamente.")
        return redirect("academics:dept_list")
    except IntegrityError:
        messages.error(request, "Ya existe un departamento con ese nombre.")
        return render(request, "academics/department_form.html", {"obj": d, "nombre": nombre, "icono": icono})

@login_required
def dept_delete(request, pk: int):
    d = get_object_or_404(Department, pk=pk)
    if request.method == "GET":
        return render(request, "academics/confirm_delete.html", {
            "object": d,
            "cancel_url": reverse("academics:dept_list"),
            "title": "Eliminar Departamento"
        })

    try:
        d.delete()
        messages.success(request, "Se eliminó correctamente.")
    except (ProtectedError, IntegrityError):
        messages.error(request, "No se pudo eliminar: hay materias asignadas a este departamento.")
    return redirect("academics:dept_list")

# -------- Materia --------
@login_required
def materia_list(request):
    q = (request.GET.get("q") or "").strip()
    dept_id = request.GET.get("department")

    qs = (Materia.objects
            .select_related("departamento")
            .filter(eliminado=False)
            .order_by("nombre"))

    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(departamento__nombre__icontains=q))

    if dept_id:
        qs = qs.filter(departamento_id=dept_id)

    departamentos = Department.objects.all().order_by("nombre")
    return render(request, "academics/materia_list.html", {
        "materias": qs,
        "q": q,
        "departamentos": departamentos,
        "selected_department": int(dept_id) if dept_id else None,
        "create_url": "academics:materia_create",
        "update_name": "academics:materia_update",
        "delete_name": "academics:materia_delete",
    })


@login_required
def materia_create(request):
    departamentos = Department.objects.all().order_by("nombre")

    if request.method == "POST":
        nombre = (request.POST.get("nombre") or "").strip()
        departamento_id = request.POST.get("departamento")
        descripcion = (request.POST.get("descripcion") or "").strip()
        icono = (request.POST.get("icono") or "").strip()
        imagen = request.FILES.get("imagen")

        # objeto temporal para repoblar el form si hay errores
        materia_tmp = Materia(
            nombre=nombre,
            descripcion=descripcion or None,
            icono=icono or None,
        )
        if departamento_id:
            try:
                materia_tmp.departamento_id = int(departamento_id)
            except ValueError:
                pass

        if not nombre or not departamento_id:
            messages.error(request, "Nombre y Departamento son obligatorios.")
            return render(request, "academics/materia_form.html", {
                "materia": materia_tmp,
                "departamentos": departamentos,
            })

        try:
            m = Materia(
                nombre=nombre,
                departamento_id=int(departamento_id),
                descripcion=descripcion or None,
                icono=icono or None,
            )
            if imagen:
                m.imagen = imagen
            m.save()
            messages.success(request, "Se creó correctamente.")
            return redirect("academics:materia_list")
        except IntegrityError:
            messages.error(request, "Ya existe una materia con ese nombre.")
            return render(request, "academics/materia_form.html", {
                "materia": materia_tmp,
                "departamentos": departamentos,
            })

    # GET
    return render(request, "academics/materia_form.html", {
        "materia": None,                      # <-- importante para “Nueva Materia”
        "departamentos": departamentos,
    })


@login_required
def materia_update(request, pk: int):
    materia = get_object_or_404(Materia, pk=pk, eliminado=False)
    departamentos = Department.objects.all().order_by("nombre")

    if request.method == "POST":
        nombre = (request.POST.get("nombre") or "").strip()
        departamento_id = request.POST.get("departamento")
        descripcion = (request.POST.get("descripcion") or "").strip()
        icono = (request.POST.get("icono") or "").strip()
        imagen = request.FILES.get("imagen")

        if not nombre or not departamento_id:
            messages.error(request, "Nombre y Departamento son obligatorios.")
            # reflejar lo editado sin perder lo actual
            materia.nombre = nombre
            materia.descripcion = descripcion or None
            materia.icono = icono or None
            try:
                materia.departamento_id = int(departamento_id)
            except (TypeError, ValueError):
                pass
            return render(request, "academics/materia_form.html", {
                "materia": materia,             # <-- clave para “Editar Materia” y precarga
                "departamentos": departamentos,
            })

        try:
            materia.nombre = nombre
            materia.departamento_id = int(departamento_id)
            materia.descripcion = descripcion or None
            materia.icono = icono or None
            if imagen:
                materia.imagen = imagen
            materia.save()
            messages.success(request, "Se actualizó correctamente.")
            return redirect("academics:materia_list")
        except IntegrityError:
            messages.error(request, "Ya existe una materia con ese nombre.")
            return render(request, "academics/materia_form.html", {
                "materia": materia,
                "departamentos": departamentos,
            })

    # GET
    return render(request, "academics/materia_form.html", {
        "materia": materia,                    # <-- objeto real
        "departamentos": departamentos,
    })


@login_required
def materia_delete(request, pk: int):
    materia = get_object_or_404(Materia, pk=pk)
    if request.method == "POST":
        try:
            materia.delete()
            messages.success(request, "Se eliminó correctamente.")
        except (ProtectedError, IntegrityError):
            messages.error(request, "No se pudo eliminar: hay comisiones/años asociados a esta materia.")
        return redirect("academics:materia_list")

    return render(request, "academics/confirm_delete.html", {
        "object": materia,
        "cancel_url": reverse("academics:materia_list"),
        "title": "Eliminar Materia",
    })

#-------- Comisión --------
@login_required
def comision_list(request):
    q = (request.GET.get("q") or "").strip()
    year = (request.GET.get("year") or "").strip()

    qs = Comision.objects.all().order_by("nombre")
    if q:
        qs = qs.filter(nombre__icontains=q)

    if year.isdigit():
        year_int = int(year)
        # Solo comisiones que tengan al menos una MCA en ese año
        subq = MateriaComisionAnio.objects.filter(comision_id=OuterRef("pk"), anio=year_int)
        qs = qs.annotate(has_year=Exists(subq)).filter(has_year=True)

    years = (MateriaComisionAnio.objects.order_by("-anio")
                .values_list("anio", flat=True).distinct())

    return render(request, "academics/comision_list_admin.html", {
        "comisiones": qs,
        "q": q,
        "years": years,
        "selected_year": int(year) if year.isdigit() else None,
        "create_url": "academics:comision_create",
        "update_name": "academics:comision_update",
        "delete_name": "academics:comision_delete",
    })

@login_required
def comision_create(request):
    departamentos = Department.objects.prefetch_related("materias").order_by("nombre")
    profesores = (User.objects
                    .filter(rol=User.Role.PROFESOR, is_active=True)
                    .order_by("last_name", "first_name"))

    if request.method == "GET":
        return render(request, "academics/comision_form.html", {
            "departamentos": departamentos,
            "profesores": profesores,
        })

    # Datos de la comisión
    nombre = (request.POST.get("nombre") or "").strip()
    icono = (request.POST.get("icono") or "").strip()
    imagen = request.FILES.get("imagen")

    if not nombre:
        messages.error(request, "El nombre es obligatorio.")
        return render(request, "academics/comision_form.html", {
            "departamentos": departamentos, "profesores": profesores,
            "nombre": nombre, "icono": icono
        })

    try:
        c = Comision(nombre=nombre, icono=icono)
        if imagen:
            c.imagen = imagen
        c.save()
        messages.success(request, "Comisión creada.")

        # --- Asignación opcional: Materia + Año + (docentes) ---
        m_id = request.POST.get("mca_materia")
        anio = request.POST.get("mca_anio")
        titular_id = request.POST.get("mca_titular")
        jtp_id = request.POST.get("mca_jtp")
        ayudante_id = request.POST.get("mca_ayudante")

        if m_id and anio and anio.isdigit():
            try:
                MateriaComisionAnio.objects.create(
                    materia_id=int(m_id),
                    comision=c,
                    anio=int(anio),
                    titular_id=int(titular_id) if titular_id else None,
                    jtp_id=int(jtp_id) if jtp_id else None,
                    ayudante_id=int(ayudante_id) if ayudante_id else None,
                )
                messages.success(request, "Asignación Materia+Año creada.")
            except IntegrityError:
                messages.error(request, "Ya existe una asignación para esa Materia/Año en esta Comisión.")

        return redirect("academics:comision_list")

    except IntegrityError:
        messages.error(request, "Ya existe una comisión con ese nombre.")
        return render(request, "academics/comision_form.html", {
            "departamentos": departamentos, "profesores": profesores,
            "nombre": nombre, "icono": icono
        })

@login_required
def comision_update(request, pk: int):
    c = get_object_or_404(Comision, pk=pk)
    departamentos = Department.objects.prefetch_related("materias").order_by("nombre")
    profesores = (User.objects
                    .filter(rol=User.Role.PROFESOR, is_active=True)
                    .order_by("last_name", "first_name"))

    if request.method == "GET":
        asignaciones = (MateriaComisionAnio.objects
                        .select_related("materia", "titular", "jtp", "ayudante")
                        .filter(comision=c).order_by("-anio", "materia__nombre"))
        return render(request, "academics/comision_form.html", {
            "obj": c,
            "nombre": c.nombre,
            "icono": c.icono or "",
            "departamentos": departamentos,
            "profesores": profesores,
            "asignaciones": asignaciones,
        })

    # actualizar comisión
    nombre = (request.POST.get("nombre") or "").strip()
    icono = (request.POST.get("icono") or "").strip()
    imagen = request.FILES.get("imagen")

    if not nombre:
        messages.error(request, "El nombre es obligatorio.")
        return render(request, "academics/comision_form.html", {
            "obj": c, "nombre": nombre, "icono": icono,
            "departamentos": departamentos, "profesores": profesores
        })

    c.nombre = nombre
    c.icono = icono
    if imagen:
        c.imagen = imagen

    try:
        c.save()
        messages.success(request, "Comisión actualizada.")
    except IntegrityError:
        messages.error(request, "Ya existe una comisión con ese nombre.")
        return render(request, "academics/comision_form.html", {
            "obj": c, "nombre": nombre, "icono": icono,
            "departamentos": departamentos, "profesores": profesores
        })

    # --- Asignación opcional: Materia + Año + (docentes) ---
    m_id = request.POST.get("mca_materia")
    anio = request.POST.get("mca_anio")
    titular_id = request.POST.get("mca_titular")
    jtp_id = request.POST.get("mca_jtp")
    ayudante_id = request.POST.get("mca_ayudante")

    if m_id and anio and anio.isdigit():
        try:
            MateriaComisionAnio.objects.create(
                materia_id=int(m_id),
                comision=c,
                anio=int(anio),
                titular_id=int(titular_id) if titular_id else None,
                jtp_id=int(jtp_id) if jtp_id else None,
                ayudante_id=int(ayudante_id) if ayudante_id else None,
            )
            messages.success(request, "Asignación Materia+Año creada.")
        except IntegrityError:
            messages.error(request, "Ya existe una asignación para esa Materia/Año en esta Comisión.")

    return redirect("academics:comision_update", pk=c.pk)

@login_required
def comision_delete(request, pk: int):
    c = get_object_or_404(Comision, pk=pk)
    if request.method == "GET":
        return render(request, "academics/confirm_delete.html", {
            "object": c,
            "cancel_url": reverse("academics:comision_list"),
            "title": "Eliminar Comisión"
        })

    try:
        c.delete()
        messages.success(request, "Se eliminó correctamente.")
    except (ProtectedError, IntegrityError):
        messages.error(request, "No se pudo eliminar: hay asignaciones (Materia+Año) vinculadas.")
    return redirect("academics:comision_list")


# -------- Esto no es de Admin --------
@login_required
def editar_resena_mca(request, mca_id):
    """
    Edita la reseña existente del user para este MCA.
    Usa el mismo template de evaluar (evaluar_mca.html) pero con is_edit=True.
    """
    u = request.user
    mca = get_object_or_404(
        MateriaComisionAnio.objects.select_related("materia", "comision", "titular", "jtp"),
        pk=mca_id
    )

    # Debe existir reseña del usuario para este MCA; si no, redirigir a crear
    resena = Resena.objects.filter(alumno=u, mca=mca).first()
    if not resena:
        messages.info(request, "Aún no enviaste una reseña para esta cursada. Podés crearla ahora.")
        return redirect('academics:evaluar_mca', mca_id=mca.id)

    # Precarga para el template
    initial = {}
    items = {i.target_type: i for i in resena.items.all()}
    it = items.get(ResenaItem.Target.MATERIA)
    if it: initial.update(materia_score=it.puntuacion, materia_comment=it.comentario)
    it = items.get(ResenaItem.Target.COMISION)
    if it: initial.update(comision_score=it.puntuacion, comision_comment=it.comentario)
    it = items.get(ResenaItem.Target.TITULAR)
    if it: initial.update(titular_score=it.puntuacion, titular_comment=it.comentario)
    it = items.get(ResenaItem.Target.JTP)
    if it: initial.update(jtp_score=it.puntuacion, jtp_comment=it.comentario)

    if request.method == "POST":
        data = request.POST

        def upsert_item(target, score_key, comment_key):
            puntuacion = (data.get(score_key) or "").strip()
            comentario = (data.get(comment_key) or "").strip()

            # Si no se envía puntaje, eliminar el item si existía
            if not puntuacion:
                ResenaItem.objects.filter(resena=resena, target_type=target).delete()
                return

            item, _ = ResenaItem.objects.get_or_create(resena=resena, target_type=target)
            item.puntuacion = int(puntuacion)
            item.comentario = comentario

            # Vincular FK según target (y limpiar las demás)
            if target == ResenaItem.Target.MATERIA:
                item.materia = mca.materia
                item.comision = item.titular = item.jtp = None
            elif target == ResenaItem.Target.COMISION:
                item.comision = mca.comision
                item.materia = item.titular = item.jtp = None
            elif target == ResenaItem.Target.TITULAR:
                if not mca.titular_id:
                    ResenaItem.objects.filter(resena=resena, target_type=target).delete()
                    return
                item.titular = mca.titular
                item.materia = item.comision = item.jtp = None
            elif target == ResenaItem.Target.JTP:
                if not mca.jtp_id:
                    ResenaItem.objects.filter(resena=resena, target_type=target).delete()
                    return
                item.jtp = mca.jtp
                item.materia = item.comision = item.titular = None

            item.save()  # valida con clean()

        upsert_item(ResenaItem.Target.MATERIA,  "materia_score",  "materia_comment")
        upsert_item(ResenaItem.Target.COMISION, "comision_score", "comision_comment")
        upsert_item(ResenaItem.Target.TITULAR,  "titular_score",  "titular_comment")
        upsert_item(ResenaItem.Target.JTP,      "jtp_score",      "jtp_comment")

        messages.success(request, "¡Listo! Tu reseña fue actualizada.")
        return redirect('people:perfil')  # o tu destino preferido

    ctx = {
        "mca": mca,
        "titular": mca.titular,
        "jtp": mca.jtp,
        "materia_score":  initial.get("materia_score", ""),
        "materia_comment":initial.get("materia_comment", ""),
        "comision_score": initial.get("comision_score", ""),
        "comision_comment":initial.get("comision_comment", ""),
        "titular_score":  initial.get("titular_score", ""),
        "titular_comment":initial.get("titular_comment", ""),
        "jtp_score":      initial.get("jtp_score", ""),
        "jtp_comment":    initial.get("jtp_comment", ""),
        "is_edit": True,  # <- para que el botón diga “Editar”
    }
    return render(request, "academics/evaluar_mca.html", ctx)



@login_required
def eliminar_resena_mca(request, mca_id):
    if request.method != "POST":
        raise Http404()

    u = request.user
    mca = get_object_or_404(MateriaComisionAnio, pk=mca_id)

    # 🧹 Eliminar SOLO la reseña (sus items se borran por cascade)
    Resena.objects.filter(alumno=u, mca=mca).delete()

    messages.success(request, "Se eliminó tu reseña. Podés volver a evaluarla cuando quieras.")
    return redirect("people:perfil") 


#CRUD DE CENSORED WORDS
class CensoredWordListView(ListView):
    model = CensoredWord
    template_name = 'academics/censoredword_list.html'

class CensoredWordCreateView(CreateView):
    model = CensoredWord
    fields = ['palabra']
    success_url = reverse_lazy('academics:censoredword_list')
    
    def form_valid(self, form):
        form.save()
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return super().form_valid(form)

class CensoredWordUpdateView(UpdateView):
    model = CensoredWord
    fields = ['palabra']
    success_url = reverse_lazy('academics:censoredword_list')
    
    def form_valid(self, form):
        form.save()
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return super().form_valid(form)

class CensoredWordDeleteView(DeleteView):
    model = CensoredWord
    success_url = reverse_lazy('academics:censoredword_list')
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return JsonResponse({'success': True})

