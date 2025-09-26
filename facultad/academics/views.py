from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Max
from django.shortcuts import get_object_or_404, render
from django.utils.timezone import localtime

from academics.models import MateriaComisionAnio, ResenaItem, Materia
from people.models import User

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

    items_qs = (
        ResenaItem.objects
        .filter(target_type="COMISION", resena__mca=mca, comision_id=comision_id)
        .order_by("-created_at")
    )
    agg = items_qs.aggregate(promedio=Avg("puntuacion"), cantidad=Count("id"))
    promedio = float(agg["promedio"] or 0.0)
    cantidad = int(agg["cantidad"] or 0)
    full_stars = int(round(promedio)) if cantidad else 0
    full_stars = max(0, min(5, full_stars))
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
        "academics/perfil_comision.html",
        {
            "materia": materia,
            "comision": comision,
            "anio": anio,
            "titular": mca.titular,   
            "jtp": mca.jtp,           
            "rating": rating,
            "comentarios": comentarios,
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

    items_qs = (
        ResenaItem.objects
        .filter(target_type="MATERIA", resena__mca__materia_id=materia_id)
        .order_by("-created_at")
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
        },
    )