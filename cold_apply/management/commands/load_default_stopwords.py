from django.core.management.base import BaseCommand
from cold_apply.load_default_stopwords import load_default_stopwords

class Command(BaseCommand):
    help = 'Loads default stopwords into the StopwordGroup model'

    def handle(self, *args, **kwargs):
        load_default_stopwords()
        self.stdout.write(self.style.SUCCESS('✔ Stopwords loaded successfully.'))
