# academics/forms.py
from django import forms
from django.core.files.base import ContentFile
from urllib.parse import urlparse, unquote
import os, requests

from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory
from .models import Department, Materia, Comision, MateriaComisionAnio

User = get_user_model()

# ---------- helpers ----------
def _filename_from_url(url: str, default='file'):
    p = urlparse(url)
    name = os.path.basename(p.path) or default
    return unquote(name)

def _download(url: str) -> ContentFile:
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return ContentFile(r.content)

# ========== Department ==========
class DepartmentForm(forms.ModelForm):
    icono_url  = forms.URLField(required=False, label="Icono (URL)",
                                widget=forms.URLInput(attrs={"placeholder": "https://... (SVG/imagen)"}))
    imagen_url = forms.URLField(required=False, label="Imagen (URL)",
                                widget=forms.URLInput(attrs={"placeholder": "https://... (JPG/PNG/SVG)"}))

    class Meta:
        model = Department
        fields = ["nombre"]  
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("nombre", "icono_url", "imagen_url"):
            if name in self.fields:
                self.fields[name].widget.attrs.update({
                    "class": "dep-input",
                    "style": "width:100%;max-width:100%;box-sizing:border-box;"
                })
        inst = self.instance
        if inst and getattr(inst, "icono", None):
            try:
                if hasattr(inst.icono, "url"):
                    self.fields["icono_url"].initial = inst.icono.url
                else:
                    self.fields["icono_url"].initial = getattr(inst, "icono", "")
            except Exception:
                pass
        if inst and getattr(inst, "imagen", None):
            try:
                if hasattr(inst.imagen, "url"):
                    self.fields["imagen_url"].initial = inst.imagen.url
            except Exception:
                pass

    def save(self, commit=True):
        obj = super().save(commit=False)

        # ICONO
        val_icono = (self.cleaned_data.get("icono_url") or "").strip()
        if val_icono:
            if hasattr(obj, "icono") and hasattr(getattr(obj, "icono"), "save"):
                try:
                    obj.icono.delete(save=False)
                except Exception:
                    pass
                obj.icono.save(_filename_from_url(val_icono, "icono"), _download(val_icono), save=False)
            else:
                obj.icono = val_icono
        else:
            if hasattr(obj, "icono"):
                if hasattr(getattr(obj, "icono"), "delete"):
                    try: obj.icono.delete(save=False)
                    except Exception: pass
                    obj.icono = None
                else:
                    obj.icono = None

        # IMAGEN
        val_img = (self.cleaned_data.get("imagen_url") or "").strip()
        if val_img:
            try:
                obj.imagen.delete(save=False)
            except Exception:
                pass
            obj.imagen.save(_filename_from_url(val_img, "imagen"), _download(val_img), save=False)
        else:
            if getattr(obj, "imagen", None):
                try: obj.imagen.delete(save=False)
                except Exception: pass
                obj.imagen = None

        if commit:
            obj.save()
        return obj


# ========== Materia ==========
class MateriaForm(forms.ModelForm):
    icono_url  = forms.URLField(required=False, label="Icono (URL)",
                                widget=forms.URLInput(attrs={"placeholder": "https://... (SVG/imagen)"}))
    imagen_url = forms.URLField(required=False, label="Imagen (URL)",
                                widget=forms.URLInput(attrs={"placeholder": "https://... (JPG/PNG/SVG)"}))

    class Meta:
        model = Materia
        fields = ["nombre", "departamento", "descripcion",] 
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
        if inst and hasattr(inst, "icono"):
            try:
                if hasattr(inst.icono, "url"):
                    self.fields["icono_url"].initial = inst.icono.url
                else:
                    self.fields["icono_url"].initial = getattr(inst, "icono", "")
            except Exception:
                pass

    def save(self, commit=True):
        obj = super().save(commit=False)

        # IMAGEN
        url_img = (self.cleaned_data.get("imagen_url") or "").strip()
        if url_img:
            try:
                obj.imagen.delete(save=False)
            except Exception:
                pass
            obj.imagen.save(_filename_from_url(url_img, "imagen"), _download(url_img), save=False)
        else:
            if getattr(obj, "imagen", None):
                try: obj.imagen.delete(save=False)
                except Exception: pass
                obj.imagen = None

        # ICONO
        url_ico = (self.cleaned_data.get("icono_url") or "").strip()
        if url_ico:
            if hasattr(obj, "icono") and hasattr(getattr(obj, "icono"), "save"):
                try:
                    obj.icono.delete(save=False)
                except Exception:
                    pass
                obj.icono.save(_filename_from_url(url_ico, "icono"), _download(url_ico), save=False)
            else:
                obj.icono = url_ico
        else:
            if hasattr(obj, "icono"):
                if hasattr(getattr(obj, "icono"), "delete"):
                    try: obj.icono.delete(save=False)
                    except Exception: pass
                    obj.icono = None
                else:
                    obj.icono = None

        if commit:
            obj.save()
        return obj


# ========== Comisión ==========
class ComisionForm(forms.ModelForm):
    icono_url  = forms.URLField(required=False, label="Icono (URL)",
                                widget=forms.URLInput(attrs={"placeholder": "https://... (SVG/imagen)"}))
    imagen_url = forms.URLField(required=False, label="Imagen (URL)",
                                widget=forms.URLInput(attrs={"placeholder": "https://... (JPG/PNG/SVG)"}))

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
        if inst and hasattr(inst, "icono"):
            try:
                if hasattr(inst.icono, "url"):
                    self.fields["icono_url"].initial = inst.icono.url
                else:
                    self.fields["icono_url"].initial = getattr(inst, "icono", "")
            except Exception:
                pass

    def save(self, commit=True):
        obj = super().save(commit=False)

        url_img = (self.cleaned_data.get("imagen_url") or "").strip()
        if url_img:
            try:
                obj.imagen.delete(save=False)
            except Exception:
                pass
            obj.imagen.save(_filename_from_url(url_img, "imagen"), _download(url_img), save=False)
        else:
            if getattr(obj, "imagen", None):
                try: obj.imagen.delete(save=False)
                except Exception: pass
                obj.imagen = None

        url_ico = (self.cleaned_data.get("icono_url") or "").strip()
        if url_ico:
            if hasattr(obj, "icono") and hasattr(getattr(obj, "icono"), "save"):
                try:
                    obj.icono.delete(save=False)
                except Exception:
                    pass
                obj.icono.save(_filename_from_url(url_ico, "icono"), _download(url_ico), save=False)
            else:
                obj.icono = url_ico
        else:
            if hasattr(obj, "icono"):
                if hasattr(getattr(obj, "icono"), "delete"):
                    try: obj.icono.delete(save=False)
                    except Exception: pass
                    obj.icono = None
                else:
                    obj.icono = None

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
        qs_doc = User.objects.filter(rol=User.Role.PROFESOR, is_active=True) \
                               .order_by("last_name", "first_name")
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
