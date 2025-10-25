# academics/forms.py
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from urllib.parse import urlparse, unquote
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory
import os, base64, requests

from .models import Department, Materia, Comision, MateriaComisionAnio

User = get_user_model()

# ----------------- Helpers -----------------
HEADERS_BROWSER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}

def _filename_from_url(url: str, default='file'):
    p = urlparse(url)
    name = os.path.basename(p.path) or default
    return unquote(name)

def _es_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")

def _es_svg_inline(s: str) -> bool:
    return s.lstrip().startswith("<svg")

def _es_data_uri_svg(s: str) -> bool:
    return s.startswith("data:image/svg+xml")

def _from_media_url_to_name(url: str) -> str | None:
    """
    Convierte '/media/dir/archivo.png' -> 'dir/archivo.png' si existe físicamente en MEDIA_ROOT.
    """
    mu = settings.MEDIA_URL
    if not mu:
        return None
    if url.startswith(mu):
        rel = url[len(mu):]
        abspath = os.path.join(settings.MEDIA_ROOT, rel.replace("/", os.sep))
        return rel if os.path.exists(abspath) else None
    return None


# ========== Department ==========
class DepartmentForm(forms.ModelForm):
    icono_url  = forms.CharField(
        required=False, label="Icono (URL o SVG)",
        widget=forms.TextInput(attrs={"placeholder": "https://... (PNG/SVG) o <svg>...</svg>"}))
    imagen_url = forms.CharField(
        required=False, label="Imagen (URL)",
        widget=forms.TextInput(attrs={"placeholder": "https://... (JPG/PNG/SVG) o /media/..."}))

    class Meta:
        model = Department
        fields = ["nombre"]
        widgets = {"nombre": forms.TextInput(attrs={"class": "form-control"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = self.instance
        # iniciales para edición
        if inst and getattr(inst, "imagen", None):
            try:
                if hasattr(inst.imagen, "url"):
                    self.fields["imagen_url"].initial = inst.imagen.url
            except Exception:
                pass
        if inst and getattr(inst, "icono", None):
            self.fields["icono_url"].initial = inst.icono

    def save(self, commit=True):
        obj = super().save(commit=False)

        # ---------- IMAGEN ----------
        url_img = (self.cleaned_data.get("imagen_url") or "").strip()
        if "imagen_url" in self.changed_data and url_img:
            if _es_url(url_img):
                try:
                    r = requests.get(url_img, timeout=15, headers=HEADERS_BROWSER)
                    if r.status_code != 200:
                        raise ValidationError({"imagen_url": f"No se pudo descargar (HTTP {r.status_code})."})
                    try:
                        if getattr(obj, "imagen", None):
                            obj.imagen.delete(save=False)
                    except Exception:
                        pass
                    obj.imagen.save(_filename_from_url(url_img, "imagen"), ContentFile(r.content), save=False)
                except ValidationError:
                    raise
                except Exception as ex:
                    raise ValidationError({"imagen_url": f"No se pudo descargar la imagen: {ex}"})
            else:
                # /media/... existente
                rel = _from_media_url_to_name(url_img) if settings.MEDIA_URL else None
                if rel:
                    obj.imagen.name = rel
                else:
                    raise ValidationError({"imagen_url": "Ingresá una URL http(s) válida o una ruta /media/... existente."})

        # ---------- ICONO (CharField) ----------
        val_ico = (self.cleaned_data.get("icono_url") or "").strip()
        if "icono_url" in self.changed_data and val_ico:
            if _es_svg_inline(val_ico) or _es_data_uri_svg(val_ico) or _es_url(val_ico) or val_ico.startswith("/"):
                obj.icono = val_ico
            else:
                obj.icono = val_ico  # lo aceptamos como texto

        if commit:
            obj.save()
        return obj


# ========== Materia ==========
class MateriaForm(forms.ModelForm):
    icono_url  = forms.CharField(
        required=False, label="Icono (URL o SVG)",
        widget=forms.TextInput(attrs={"placeholder": "https://... (PNG/SVG) o <svg>...</svg>"}))
    imagen_url = forms.CharField(
        required=False, label="Imagen (URL)",
        widget=forms.TextInput(attrs={"placeholder": "https://... (JPG/PNG/SVG) o /media/..."}))

    class Meta:
        model = Materia
        fields = ["nombre", "departamento", "descripcion"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "departamento": forms.Select(attrs={"class": "form-select"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = self.instance
        if inst and getattr(inst, "imagen", None):
            try:
                if hasattr(inst.imagen, "url"):
                    self.fields["imagen_url"].initial = inst.imagen.url
            except Exception:
                pass
        if inst and getattr(inst, "icono", None):
            self.fields["icono_url"].initial = inst.icono

    def save(self, commit=True):
        obj = super().save(commit=False)

        # ---------- IMAGEN ----------
        url_img = (self.cleaned_data.get("imagen_url") or "").strip()
        if "imagen_url" in self.changed_data and url_img:
            if _es_url(url_img):
                try:
                    r = requests.get(url_img, timeout=15, headers=HEADERS_BROWSER)
                    if r.status_code != 200:
                        raise ValidationError({"imagen_url": f"No se pudo descargar (HTTP {r.status_code})."})
                    try:
                        if getattr(obj, "imagen", None):
                            obj.imagen.delete(save=False)
                    except Exception:
                        pass
                    obj.imagen.save(_filename_from_url(url_img, "imagen"), ContentFile(r.content), save=False)
                except ValidationError:
                    raise
                except Exception as ex:
                    raise ValidationError({"imagen_url": f"No se pudo descargar la imagen: {ex}"})
            else:
                rel = _from_media_url_to_name(url_img) if settings.MEDIA_URL else None
                if rel:
                    obj.imagen.name = rel
                else:
                    raise ValidationError({"imagen_url": "Ingresá una URL http(s) válida o una ruta /media/... existente."})

        # ---------- ICONO (CharField) ----------
        val_ico = (self.cleaned_data.get("icono_url") or "").strip()
        if "icono_url" in self.changed_data and val_ico:
            if _es_svg_inline(val_ico) or _es_data_uri_svg(val_ico) or _es_url(val_ico) or val_ico.startswith("/"):
                obj.icono = val_ico
            else:
                obj.icono = val_ico

        if commit:
            obj.save()
        return obj


# ========== Comisión ==========
class ComisionForm(forms.ModelForm):
    icono_url  = forms.CharField(
        required=False, label="Icono (URL o SVG)",
        widget=forms.TextInput(attrs={"placeholder": "https://... (PNG/SVG) o <svg>...</svg>"}))
    imagen_url = forms.CharField(
        required=False, label="Imagen (URL)",
        widget=forms.TextInput(attrs={"placeholder": "https://... (JPG/PNG/SVG) o /media/..."}))

    class Meta:
        model = Comision
        fields = ["nombre"]
        widgets = {"nombre": forms.TextInput(attrs={"class": "form-control"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = self.instance
        if inst and getattr(inst, "imagen", None):
            try:
                if hasattr(inst.imagen, "url"):
                    self.fields["imagen_url"].initial = inst.imagen.url
            except Exception:
                pass
        if inst and getattr(inst, "icono", None):
            self.fields["icono_url"].initial = inst.icono

    def save(self, commit=True):
        obj = super().save(commit=False)

        # ---------- IMAGEN ----------
        url_img = (self.cleaned_data.get("imagen_url") or "").strip()
        if "imagen_url" in self.changed_data and url_img:
            if _es_url(url_img):
                try:
                    r = requests.get(url_img, timeout=15, headers=HEADERS_BROWSER)
                    if r.status_code != 200:
                        raise ValidationError({"imagen_url": f"No se pudo descargar (HTTP {r.status_code})."})
                    try:
                        if getattr(obj, "imagen", None):
                            obj.imagen.delete(save=False)
                    except Exception:
                        pass
                    obj.imagen.save(_filename_from_url(url_img, "imagen"), ContentFile(r.content), save=False)
                except ValidationError:
                    raise
                except Exception as ex:
                    raise ValidationError({"imagen_url": f"No se pudo descargar la imagen: {ex}"})
            else:
                rel = _from_media_url_to_name(url_img) if settings.MEDIA_URL else None
                if rel:
                    obj.imagen.name = rel
                else:
                   self.add_error("imagen_url", "Ingresá una URL http(s) válida o una ruta /media/... existente.")

        # ---------- ICONO (CharField) ----------
        val_ico = (self.cleaned_data.get("icono_url") or "").strip()
        if "icono_url" in self.changed_data and val_ico:
            if _es_svg_inline(val_ico) or _es_data_uri_svg(val_ico) or _es_url(val_ico) or val_ico.startswith("/"):
                obj.icono = val_ico
            else:
                obj.icono = val_ico

        if commit:
            obj.save()
        return obj


# ========== MCA ==========
class MCAForm(forms.ModelForm):
    class Meta:
        model = MateriaComisionAnio
        fields = ["materia", "anio", "titular", "jtp", "ayudante"]
        widgets = {
            "materia":  forms.Select(attrs={"class": "form-select"}),
            "anio":     forms.NumberInput(attrs={"class": "form-control", "min": 1990, "max": 2100}),
            "titular":  forms.Select(attrs={"class": "form-select"}),
            "jtp":      forms.Select(attrs={"class": "form-select"}),
            "ayudante": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs_doc = User.objects.filter(rol=User.Role.PROFESOR, is_active=True).order_by("last_name", "first_name")
        for k in ("titular", "jtp", "ayudante"):
            self.fields[k].queryset = qs_doc
            self.fields[k].required = False
            self.fields[k].empty_label = "— Sin asignar —"


MCAFormSet = inlineformset_factory(
    parent_model=Comision,
    model=MateriaComisionAnio,
    form=MCAForm,
    fields=["materia", "anio", "titular", "jtp", "ayudante"],
    extra=1,
    can_delete=True,
    validate_min=False,
    validate_max=False,
)
