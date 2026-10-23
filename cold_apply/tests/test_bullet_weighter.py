import json
from types import SimpleNamespace

from django.test import SimpleTestCase

from cold_apply.static.scripts.resume_writer.bullet_weighter import weigh


class WeighTest(SimpleTestCase):
    """weigh() only stems words, so it runs with the NLTK data the image has (stopwords)."""

    def test_counts_bullet_stems_found_in_the_keywords(self):
        # BUG-043: the tokenizer/tagger code that needed more NLTK data is gone
        keywords = [
            SimpleNamespace(unigram="managing", bigram="data analysis", trigram="cross functional teams"),
        ]
        bullet = SimpleNamespace(text="Managed data for three teams")
        result = json.loads(weigh(jd_keywords=keywords, bullet=bullet))
        # manag, data, team
        self.assertEqual(result["0"]["weight"], 3)
