import logging
import unicodedata

from django import forms
from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX, identify_hasher
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.template import loader
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.text import capfirst
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.views.decorators.debug import sensitive_variables
from django.contrib.auth import get_user_model

from people.validators import validate_utn_email

UserModel = get_user_model()
logger = logging.getLogger("django.contrib.auth")

class UsernameField(forms.CharField):
    def to_python(self, value):
        value = super().to_python(value)
        if self.max_length is not None and len(value) > self.max_length:
            # Normalization can increase the string length (e.g.
            # "ﬀ" -> "ff", "½" -> "1⁄2") but cannot reduce it, so there is no
            # point in normalizing invalid data. Moreover, Unicode
            # normalization is very slow on Windows and can be a DoS attack
            # vector.
            return value
        return unicodedata.normalize("NFKC", value)

    def widget_attrs(self, widget):
        return {
            **super().widget_attrs(widget),
            "autocapitalize": "none",
            "autocomplete": "username",
        }
    
class SetPasswordMixin:
    """
    Form mixin that validates and sets a password for a user.
    """

    error_messages = {
        "password_mismatch": _("The two password fields didn’t match."),
    }

    @staticmethod
    def create_password_fields(label1=_("Password"), label2=_("Password confirmation")):
        password1 = forms.CharField(
            label=label1,
            required=True,
            strip=False,
            widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
            help_text=password_validation.password_validators_help_text_html(),
        )
        password2 = forms.CharField(
            label=label2,
            required=True,
            widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
            strip=False,
            help_text=_("Enter the same password as before, for verification."),
        )
        return password1, password2

    @sensitive_variables("password1", "password2")
    def validate_passwords(
        self,
        password1_field_name="password1",
        password2_field_name="password2",
    ):
        password1 = self.cleaned_data.get(password1_field_name)
        password2 = self.cleaned_data.get(password2_field_name)

        if password1 and password2 and password1 != password2:
            error = ValidationError(
                self.error_messages["password_mismatch"],
                code="password_mismatch",
            )
            self.add_error(password2_field_name, error)

    @sensitive_variables("password")
    def validate_password_for_user(self, user, password_field_name="password2"):
        password = self.cleaned_data.get(password_field_name)
        if password:
            try:
                password_validation.validate_password(password, user)
            except ValidationError as error:
                self.add_error(password_field_name, error)

    def set_password_and_save(self, user, password_field_name="password1", commit=True):
        user.set_password(self.cleaned_data[password_field_name])
        if commit:
            user.save()
        return user

class BaseUserCreationForm(SetPasswordMixin, forms.ModelForm):
    """
    A form that creates a user, with no privileges, from the given username and
    password.

    This is the documented base class for customizing the user creation form.
    It should be kept mostly unchanged to ensure consistency and compatibility.
    """

    password1, password2 = SetPasswordMixin.create_password_fields()

    class Meta:
        model = User
        fields = ("username",)
        field_classes = {"username": UsernameField}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self._meta.model.USERNAME_FIELD in self.fields:
            self.fields[self._meta.model.USERNAME_FIELD].widget.attrs[
                "autofocus"
            ] = True

    def clean(self):
        self.validate_passwords()
        return super().clean()

    def _post_clean(self):
        super()._post_clean()
        # Validate the password after self.instance is updated with form data
        # by super().
        self.validate_password_for_user(self.instance)

    def save(self, commit=True):
        user = super().save(commit=False)
        user = self.set_password_and_save(user, commit=commit)
        if commit and hasattr(self, "save_m2m"):
            self.save_m2m()
        return user

class UserCreationForm(BaseUserCreationForm):
    class Meta(BaseUserCreationForm.Meta):
        model  = UserModel
        fields = ("username", "first_name", "last_name", "email", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.username = self.cleaned_data["username"]
        # BaseUserCreationForm no setea email por sí solo
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if username and self._meta.model.objects.filter(username__iexact=username).exists():
            raise ValidationError(
                self.instance.unique_error_message(self._meta.model, ["username"])
            )
        return username
    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and self._meta.model.objects.filter(email__iexact=email).exists():
            raise ValidationError("Ya existe un usuario con este email.")
        return email

class SignupForm(forms.Form):
    first_name = forms.CharField(label="Nombre", max_length=150)
    last_name  = forms.CharField(label="Apellido", max_length=150)
    username   = forms.CharField(label="Usuario", max_length=150, required=False, widget=forms.HiddenInput())
    legajo     = forms.CharField(label="Legajo", max_length=50, required=False)

    def signup(self, request, user):
        # El email ya fue validado por CustomAccountAdapter
        user.first_name = self.cleaned_data["first_name"]
        user.last_name  = self.cleaned_data["last_name"]
        
        if not user.username:
            user.username = make_unique_username(user.first_name, user.last_name, user.email)
        
        user.legajo = self.cleaned_data.get("legajo") or None

        if hasattr(user, "rol") and hasattr(UserModel, "Role"):
            user.rol = UserModel.Role.ALUMNO

        user.save()
        return user
    
from django.utils.text import slugify

def make_unique_username(first_name: str, last_name: str, email: str | None = None) -> str:
    base = slugify(f"{(first_name or '').strip()}.{(last_name or '').strip()}")  # joaquin.luberto
    base = base.replace("-", ".").strip(".")
    if not base:
        # fallback si no hay nombre/apellido (o son vacíos)
        base = slugify((email or "user").split("@")[0]) or "user"

    max_len = UserModel._meta.get_field("username").max_length
    base = base[:max_len]

    username = base
    i = 1
    while UserModel.objects.filter(username__iexact=username).exists():
        suf = str(i)
        username = f"{base[:max_len - len(suf)]}{suf}"
        i += 1
    return username