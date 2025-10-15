# academics/plan_loader.py
import csv, json, os
from functools import lru_cache
from django.conf import settings

def _normalize_rows(rows):
    norm = []
    for i, row in enumerate(rows, start=1):
        nombre = (row.get("materia") or "").strip()
        if not nombre:
            continue
        try:
            anio = int(row.get("anio") or 1)
            cuat = int(row.get("cuatrimestre") or 1)
            orden = int(row.get("orden") or i)
        except ValueError:
            anio, cuat, orden = 1, 1, i
        carrera = (row.get("carrera") or "Sin especificar").strip()
        norm.append({
            "materia": nombre,
            "anio": anio,
            "carrera": carrera,
        })
    norm.sort(key=lambda x: (x["carrera"], x["anio"], x["materia"]))
    return tuple(norm)

@lru_cache(maxsize=1)
def load_plan_rows():
    path = getattr(settings, "ACADEMICS_PLAN_PATH", None)
    if not path or not os.path.exists(path):
        return tuple()

    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".json":
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    return tuple()
                return _normalize_rows(data)
        elif ext == ".csv":
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                return _normalize_rows(list(reader))
        else:
            return tuple()
    except Exception:
        return tuple()
