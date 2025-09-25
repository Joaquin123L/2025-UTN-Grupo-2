# seed_resenas_am1_s21_2025.py
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Avg
from academics.models import Materia, Comision, MateriaComisionAnio, Resena, ResenaItem

User = get_user_model()

def get_or_create_person(username, first_name="", last_name=""):
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={"first_name": first_name, "last_name": last_name},
    )
    return user

def run():
    with transaction.atomic():
        # Base académica
        materia, _ = Materia.objects.get_or_create(nombre="Análisis Matemático 1")
        comision, _ = Comision.objects.get_or_create(nombre="S21")

        # Personas (titular y JTP)
        titular = get_or_create_person("christian.occhiuto", "Christian", "Occhiuto")
        jtp     = get_or_create_person("lucia.a.barrios", "Lucía A.", "Barrios")

        # Cursada 2025 (MateriaComisionAnio)
        mca, _ = MateriaComisionAnio.objects.get_or_create(
            materia=materia,
            comision=comision,
            anio=2025,
            defaults={"titular": titular, "jtp": jtp}
        )
        # Asegurar roles actualizados por si ya existía
        changed = False
        if getattr(mca, "titular_id", None) != titular.id:
            mca.titular = titular
            changed = True
        if getattr(mca, "jtp_id", None) != jtp.id:
            mca.jtp = jtp
            changed = True
        if changed:
            mca.save(update_fields=["titular", "jtp"])

        # 6 alumnos
        alumnos = []
        for i in range(1, 7):
            u, _ = User.objects.get_or_create(
                username=f"alumno{i}",
                defaults={"first_name": f"Alumno{i}", "last_name": "Demo"}
            )
            alumnos.append(u)

        # Reseñas de ejemplo (aptas)
        data_resenas = [
            dict(pm=5, cm="La materia estuvo muy bien organizada y clara.",
                 pc=5, cc="La comisión tuvo un excelente clima de trabajo.",
                 pt=5, ct="El profesor explicó con mucha claridad.",
                 pj=4, cj="Muy buena predisposición para responder dudas."),
            dict(pm=4, cm="El contenido es exigente pero bien estructurado.",
                 pc=4, cc="Se cumplió con el programa en tiempo y forma.",
                 pt=4, ct="Explicaciones sólidas y ejemplos prácticos.",
                 pj=5, cj="La JTP siempre resolvió consultas con paciencia."),
            dict(pm=3, cm="Materia compleja, requiere bastante estudio independiente.",
                 pc=4, cc="Las clases fueron dinámicas y bien planificadas.",
                 pt=4, ct="Buen dominio del tema.",
                 pj=3, cj="Correcta, aunque a veces difícil de seguir."),
            dict(pm=5, cm="Materia fundamental y muy bien dictada.",
                 pc=5, cc="Excelente acompañamiento en la cursada.",
                 pt=5, ct="El titular motivó a seguir aprendiendo.",
                 pj=5, cj="Muy clara y accesible en las consultas."),
            dict(pm=4, cm="Los temas de la materia fueron interesantes y útiles.",
                 pc=3, cc="Algunos trabajos prácticos resultaron extensos.",
                 pt=4, ct="Explicó bien, aunque a veces un poco rápido.",
                 pj=4, cj="La JTP ayudó mucho en la preparación de parciales."),
            dict(pm=3, cm="Materia difícil, pero necesaria en la carrera.",
                 pc=4, cc="La comisión mantuvo un buen ritmo.",
                 pt=3, ct="Correcto pero podría interactuar más con los alumnos.",
                 pj=4, cj="Muy buena predisposición en las consultas."),
        ]

        # Carga de reseñas
        for alumno, d in zip(alumnos, data_resenas):
            resena, _ = Resena.objects.get_or_create(alumno=alumno, mca=mca)

            ResenaItem.objects.update_or_create(
                resena=resena, target_type="MATERIA",
                defaults=dict(materia=materia, puntuacion=d["pm"], comentario=d["cm"])
            )
            ResenaItem.objects.update_or_create(
                resena=resena, target_type="COMISION",
                defaults=dict(comision=comision, puntuacion=d["pc"], comentario=d["cc"])
            )
            ResenaItem.objects.update_or_create(
                resena=resena, target_type="TITULAR",
                defaults=dict(titular=titular, puntuacion=d["pt"], comentario=d["ct"])
            )
            ResenaItem.objects.update_or_create(
                resena=resena, target_type="JTP",
                defaults=dict(jtp=jtp, puntuacion=d["pj"], comentario=d["cj"])
            )

        print("✅ Cargadas/actualizadas 6 reseñas para Análisis Matemático 1 - S21 (2025).")

        # Promedios (con fallback si es None)
        def fmt(x): return f"{x:.2f}" if x is not None else "s/d"

        prom_materia = ResenaItem.objects.filter(resena__mca=mca, target_type="MATERIA").aggregate(Avg("puntuacion"))["puntuacion__avg"]
        prom_comision = ResenaItem.objects.filter(resena__mca=mca, target_type="COMISION").aggregate(Avg("puntuacion"))["puntuacion__avg"]
        prom_titular = ResenaItem.objects.filter(resena__mca=mca, target_type="TITULAR").aggregate(Avg("puntuacion"))["puntuacion__avg"]
        prom_jtp     = ResenaItem.objects.filter(resena__mca=mca, target_type="JTP").aggregate(Avg("puntuacion"))["puntuacion__avg"]

        print(f"📊 Promedios — Materia: {fmt(prom_materia)} | Comisión: {fmt(prom_comision)} | Titular: {fmt(prom_titular)} | JTP: {fmt(prom_jtp)}")

# Ejecutar
run()
