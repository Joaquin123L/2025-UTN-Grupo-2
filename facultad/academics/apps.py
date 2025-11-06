from django.apps import AppConfig
from better_profanity import profanity
from django.db.utils import OperationalError, ProgrammingError

class AcademicsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'academics'

    def ready(self):
        from .models import CensoredWord
        try:
            words = [w.lower() for w in CensoredWord.objects.values_list("palabra", flat=True)]
        except (OperationalError, ProgrammingError):
            words = []

        profanity.load_censor_words()
        if words:
            profanity.add_censor_words(words)
