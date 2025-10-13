from django.core.exceptions import ValidationError

def validate_utn_email(email: str):
    allowed = "@alu.frlp.utn.edu.ar"
    if not email.lower().endswith(allowed):
        raise ValidationError(f"El email debe terminar en {allowed}.")
