#!/usr/bin/python3

import json
import string
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from cold_apply.models import KeywordAnalysis, Job, BulletKeyword



class Analyzer:
    def __init__(self, job_description: str, stopwords: list[str]):
        self.input_text = job_description.lower()
        self.stopwords = [
                ''.join(c for c in w.lower() if c not in string.punctuation)
                for w in (stopwords or [])
        ]
        self.cleaned_words = self.parse()


    def parse(self):
        text = ''.join([c for c in self.input_text if c not in string.punctuation])
        tokens = text.split()
        words = [word for word in tokens if word not in self.stopwords]
        return words

    def find_keywords(self, lower_bound, upper_bound):
        vectorizer = TfidfVectorizer(
            input='content',
            ngram_range=(lower_bound, upper_bound),
            stop_words=self.stopwords
        )
        # Use cleaned words for TF-IDF
        cleaned_text = ' '.join(self.cleaned_words)
        X_tfidf = vectorizer.fit_transform([cleaned_text])
        feature_names = vectorizer.get_feature_names_out()
        X_tfidf_df = pd.DataFrame(X_tfidf.toarray())
        X_tfidf_df.columns = feature_names
        X_tfidf_df.sort_values(by=X_tfidf_df.index[0], axis=1, inplace=True, ascending=False)
        top_twenty = X_tfidf_df.iloc[:, :20].columns.tolist()
        for i in range(len(top_twenty)):
            if len(top_twenty[i].split(' ')) > 1:
                top_twenty[i] = ' '.join(sorted(top_twenty[i].split(' ')))
        return top_twenty


# Initialize analyzer
# Pure analyzer: no DB, no categories
def analyze(job_description: str, *, stopwords: list[str]):
    if len(job_description.split()) < 5:
        job_description = (job_description + " ") * 10
    a = Analyzer(job_description, stopwords=stopwords or [])
    return {
        "unigram": a.find_keywords(1, 1),
        "bigram":  a.find_keywords(2, 2),
        "trigram": a.find_keywords(3, 3),
        }

# Hooks allowed DB access
from django.core import serializers
from cold_apply.models import KeywordAnalysis, Job

# Writes results to database
# Persist one KeywordAnalysis row (no categories)
def hook_after_jd_analysis(job_id: int, result: dict) -> None:
    job = Job.objects.get(id=job_id)
    KeywordAnalysis.objects.filter(job=job).delete()
    KeywordAnalysis.objects.create(
        job=job,
        unigram=", ".join(result.get("unigram", [])),
        bigram=", ".join(result.get("bigram", [])),
        trigram=", ".join(result.get("trigram", [])),
    )
    print('JD analysis hook completed successfully')


# Persist BulletKeyword entries (no categories)
def hook_after_bullet_analysis(bullet_id: int, items: list[dict]) -> None:
    """
    items: iterable of dicts shaped for BulletKeyword, e.g.
      {"unigram": "...", "bigram": "...", "trigram": "..."}
    """
    BulletKeyword.objects.filter(bullet_id=bullet_id).delete()
    for it in items:
        BulletKeyword.objects.create(
            bullet_id=bullet_id,
            unigram=it.get("unigram", ""),
            bigram=it.get("bigram", ""),
            trigram=it.get("trigram", ""),
        )
    print("Bullet analysis hook completed successfully")