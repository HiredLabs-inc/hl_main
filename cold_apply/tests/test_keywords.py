import json
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from cold_apply.keywords import KeywordError, extract_keywords, parse_reply, usable_phrases
from cold_apply.models import KeywordAnalysis
from cold_apply.tests.factories import JobFactory, ParticipantFactory
from hlagents.models import TaskCall
from hlagents.providers import ProviderError
from hlagents.tests.fakes import FakeProvider, answer

DESCRIPTION = (
    "We're hiring a Software Engineer. You'll write Python, Java and C++, conduct code reviews, "
    "and keep a valid security clearance. Great benefits and an equal opportunity employer."
)


def reply(unigrams=(), bigrams=(), trigrams=()):
    return answer(json.dumps({"unigrams": list(unigrams), "bigrams": list(bigrams), "trigrams": list(trigrams)}))


class UsablePhrasesTest(SimpleTestCase):
    def test_keeps_phrases_in_the_description_with_the_right_word_count(self):
        data = {
            "unigrams": ["Python", "C++", "java", "Rust", "code reviews", "Python"],
            "bigrams": ["code reviews", "Software Engineer", "reviews code", "security"],
            "trigrams": ["valid security clearance", "Python, Java and", "conduct code reviews"],
        }
        self.assertEqual(
            usable_phrases(data, DESCRIPTION),
            {
                # Rust isn't in the description, a repeat is dropped, and case is ignored
                "unigram": ["Python", "C++", "java"],
                # Reordered words and the wrong word count are dropped
                "bigram": ["code reviews", "Software Engineer"],
                # Commas separate words, so "Python, Java and" is three words found in the text
                "trigram": ["valid security clearance", "Python Java and", "conduct code reviews"],
            },
        )

    def test_whole_words_only(self):
        self.assertEqual(usable_phrases({"unigrams": ["Jav", "ware"]}, DESCRIPTION)["unigram"], [])

    def test_at_most_20_per_list(self):
        words = " ".join(f"skill{i}" for i in range(30))
        self.assertEqual(len(usable_phrases({"unigrams": words.split()}, words)["unigram"]), 20)


class ParseReplyTest(SimpleTestCase):
    def test_fenced_json(self):
        self.assertEqual(parse_reply('```json\n{"unigrams": ["SQL"]}\n```'), {"unigrams": ["SQL"]})

    def test_not_json(self):
        with self.assertRaises(KeywordError):
            parse_reply("Here are the keywords: SQL")

    def test_not_an_object(self):
        with self.assertRaises(KeywordError):
            parse_reply('["SQL"]')


class ExtractKeywordsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.participant = ParticipantFactory(jobs=[], experiences=[])
        cls.job = JobFactory(participant=cls.participant, description=DESCRIPTION)

    def extract_with(self, *replies):
        provider = FakeProvider(*replies)
        with mock.patch("hlagents.completion.get_provider", return_value=provider):
            source = extract_keywords(self.job, self.participant.user)
        return source, provider

    def rows(self):
        return list(KeywordAnalysis.objects.filter(job=self.job).order_by("pk").values_list("unigram", "bigram", "trigram"))

    def test_llm_keywords_replace_the_old_ones_and_pad_short_lists(self):
        KeywordAnalysis.objects.create(job=self.job, unigram="old", bigram="old one", trigram="old old one")
        source, provider = self.extract_with(
            reply(["Python", "Java", "C++"], ["code reviews", "Software Engineer"], ["valid security clearance"])
        )
        self.assertEqual(source, "llm")
        self.assertEqual(provider.calls[0]["messages"][1]["content"], DESCRIPTION)
        self.assertEqual(
            self.rows(),
            [
                ("Python", "code reviews", "valid security clearance"),
                ("Java", "Software Engineer", ""),
                ("C++", "", ""),
            ],
        )
        call = TaskCall.objects.get()
        self.assertEqual((call.config.key, call.user), ("job_keywords", self.participant.user))

    def assert_fell_back(self, *replies):
        with mock.patch("cold_apply.keywords.analyze", return_value=json.dumps(
            {"0": {"unigram": "python", "bigram": "java python", "trigram": "c java python"}}
        )) as analyze:
            with self.assertLogs("cold_apply.keywords", "WARNING"):
                source, _ = self.extract_with(*replies)
        self.assertEqual(source, "fallback")
        analyze.assert_called_once_with(DESCRIPTION)
        self.assertEqual(self.rows(), [("python", "java python", "c java python")])

    def test_provider_failure_falls_back(self):
        with self.assertLogs("hlagents.completion", "ERROR"):
            self.assert_fell_back(ProviderError("504 DEADLINE_EXCEEDED"))

    def test_reply_that_isnt_json_falls_back(self):
        self.assert_fell_back(answer("Python, Java"))

    def test_reply_with_nothing_usable_falls_back(self):
        self.assert_fell_back(reply(["Rust"], ["reviews code"]))

    def test_job_without_a_description_uses_the_fallback_without_calling(self):
        self.job.description = "   "
        with mock.patch("cold_apply.keywords.complete") as complete, mock.patch(
            "cold_apply.keywords.analyze", return_value="{}"
        ), self.assertLogs("cold_apply.keywords", "WARNING"):
            self.assertEqual(extract_keywords(self.job), "fallback")
        complete.assert_not_called()


class JobKeywordsViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.participant = ParticipantFactory(jobs=[], experiences=[])
        cls.job = JobFactory(participant=cls.participant, description=DESCRIPTION)

    def setUp(self):
        self.client.force_login(self.participant.user)

    def test_job_page_doesnt_wait_for_keywords(self):
        with mock.patch("cold_apply.views.extract_keywords") as extract:
            response = self.client.get(reverse("cold_apply:job_detail", args=[self.job.pk]))
        extract.assert_not_called()
        self.assertContains(response, "Finding keywords")
        self.assertContains(response, reverse("cold_apply:job_keywords", args=[self.job.pk]))

    def test_keywords_are_found_once(self):
        provider = FakeProvider(reply(["Python"], ["code reviews"], ["valid security clearance"]))
        url = reverse("cold_apply:job_keywords", args=[self.job.pk])
        with mock.patch("hlagents.completion.get_provider", return_value=provider):
            response = self.client.post(url, HTTP_HX_REQUEST="true")
            self.assertContains(response, "valid security clearance")
            self.assertNotContains(response, "Finding keywords")
            # Found already, so no second call
            self.client.post(url, HTTP_HX_REQUEST="true")
        self.assertEqual(len(provider.calls), 1)
        self.assertContains(self.client.get(reverse("cold_apply:job_detail", args=[self.job.pk])), "code reviews")
