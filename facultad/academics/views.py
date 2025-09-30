from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Max
from django.shortcuts import get_object_or_404, render, redirect
from django.utils.timezone import localtime
from academics.models import MateriaComisionAnio, ResenaItem, Materia, Nota, Resena
from people.models import User
from django.contrib import messages
from django.db import transaction, IntegrityError
from django.http import HttpResponseForbidden

@login_required
def home(request):
    return render(request, "academics/home.html")

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
            "texto": (it.comentario or "").strip(),
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
            "texto": (it.comentario or "").strip(),
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
