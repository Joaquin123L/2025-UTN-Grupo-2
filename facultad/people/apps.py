from django.apps import AppConfig
from better_profanity import profanity

SPANISH_BAD_WORDS = [
    "mierda", "boludo", "pelotudo", "forro", "concha",
    "carajo", "puta", "puto", "hdp", "pete", "culiado",
    "garca", "mogólico", "mogolico", "pelotudez"
]


class PeopleConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'people'

    def ready(self):
        profanity.load_censor_words()
        profanity.add_censor_words(SPANISH_BAD_WORDS)

