from django.db import transaction
from people.models import User
from academics.models import Materia, Comision, MateriaComisionAnio, Nota

def run():
    with transaction.atomic():
        # Alumna
        alumna, _ = User.objects.get_or_create(
            email="stefaniafrancini03@gmail.com",
            defaults=dict(username="stefania", first_name="Stefania", last_name="Francini", rol=User.Role.ALUMNO),
        )
        if alumna.rol != User.Role.ALUMNO:
            alumna.rol = User.Role.ALUMNO
            alumna.save(update_fields=["rol"])

        # Helper para profes
        def prof(nombre, apellido, username, email=None):
            if email is None: email = f"{username}@example.com"
            u, _ = User.objects.get_or_create(
                username=username,
                defaults=dict(first_name=nombre, last_name=apellido, email=email, rol=User.Role.PROFESOR),
            )
            if u.rol != User.Role.PROFESOR:
                u.rol = User.Role.PROFESOR
                u.save(update_fields=["rol"])
            if not u.has_usable_password():
                u.set_unusable_password(); u.save(update_fields=[])
            return u

        # Profes
        titular_occhiuto = prof("Christian", "Occhiuto", "cocchiuto")
        jtp_barrios      = prof("Lucia A", "Barrios", "lbarrios")
        titular_cerveri  = prof("Gustavo", "Cerveri", "gcerveri")
        jtp_jorge        = prof("Martín", "Jorge", "mjorge")

        # Materias y comisiones
        mat_anu, _ = Materia.objects.get_or_create(nombre="Análisis Numérico")
        mat_ar , _ = Materia.objects.get_or_create(nombre="Administración de Recursos")
        com_s31, _ = Comision.objects.get_or_create(nombre="S31")
        com_s41, _ = Comision.objects.get_or_create(nombre="S41")

        # MCA 2025
        mca_anu_2025, _ = MateriaComisionAnio.objects.get_or_create(
            materia=mat_anu, comision=com_s31, anio=2025,
            defaults={"titular": titular_occhiuto, "jtp": jtp_barrios}
        )
        mca_anu_2025.titular, mca_anu_2025.jtp = titular_occhiuto, jtp_barrios
        mca_anu_2025.save()

        mca_ar_2025, _ = MateriaComisionAnio.objects.get_or_create(
            materia=mat_ar, comision=com_s41, anio=2025,
            defaults={"titular": titular_cerveri, "jtp": jtp_jorge}
        )
        mca_ar_2025.titular, mca_ar_2025.jtp = titular_cerveri, jtp_jorge
        mca_ar_2025.save()

        # Notas
        Nota.objects.update_or_create(
            alumno=alumna, mca=mca_anu_2025,
            defaults={"nota": 7, "estado": Nota.Estado.APROBADA},
        )
        Nota.objects.update_or_create(
            alumno=alumna, mca=mca_ar_2025,
            defaults={"nota": 6, "estado": Nota.Estado.APROBADA},
        )

        print("✅ Listo:")
        print(f"  - {mca_anu_2025} → Nota 7 (APROBADA)")
        print(f"  - {mca_ar_2025} → Nota 6 (APROBADA)")
