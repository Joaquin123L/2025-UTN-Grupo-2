from django.apps import AppConfig
from better_profanity import profanity

SPANISH_BAD_WORDS = [
    "mierda", "boludos", "pelotudo", "forro", "concha",
    "carajo", "puta", "puto", "hdp", "pete", "culiado",
    "garca", "mogólico", "mogolico", "pelotudez"
]


class AcademicsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'academics'
    def ready(self):
        profanity.load_censor_words()
        profanity.add_censor_words(SPANISH_BAD_WORDS)
