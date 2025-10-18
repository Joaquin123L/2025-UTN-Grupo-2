from allauth.account.adapter import DefaultAccountAdapter
from django.core.exceptions import ValidationError
from people.validators import validate_utn_email


class CustomAccountAdapter(DefaultAccountAdapter):
    def clean_email(self, email):
        """
        Valida que el email sea institucional de la UTN.
        """
        email = super().clean_email(email)
        validate_utn_email(email)
        return email