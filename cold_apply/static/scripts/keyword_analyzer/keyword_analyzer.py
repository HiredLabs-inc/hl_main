#!/usr/bin/python3

import json
import string
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer



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
def analyze(job_description: str, *, stopwords_by_category: dict[str, list[str]]):
    cats = ["nltk english stopwords", "low value", "industry protected"]
    if len(job_description.split()) < 5:
        job_description = (job_description + " ") * 10
    out = {}
    for cat in cats:
        a = Analyzer(job_description, stopwords=stopwords_by_category.get(cat, []))
        out[cat] = {
            "unigram": a.find_keywords(1, 1),
            "bigram":  a.find_keywords(2, 2),
            "trigram": a.find_keywords(3, 3),
        }
    return out

# Hooks allowed DB access
from django.core import serializers
from cold_apply.models import KeywordAnalysis, Job

# Writes results to database
def hook_after_jd_analysis(task, job_id: int):
    if isinstance(task, dict):
        data = task
    else:
        data = json.loads(task)
    job = Job.objects.get(id=job_id)
    for category in data:
        unigrams = ', '.join(data[category]['unigram'])
        bigrams = ', '.join(data[category]['bigram'])
        trigrams = ', '.join(data[category]['trigram'])
        KeywordAnalysis.objects.create(
            job=job,
            category=category,
            unigram=unigrams,
            bigram=bigrams,
            trigram=trigrams,
        )
    print('JD analysis hook completed successfully')


def hook_after_bullet_analysis(task, bullet_id: int):
    data = json.loads(task)
    serialized = []
    for category in data:
        for ngram_type in data[category]:
            for value in data[category][ngram_type]:
                entry = {
                    'bullet': bullet_id,
                    'category': category,
                    'ngram_type': ngram_type,
                    'value': value
                }
                formatted = dict(
                    model='cold_apply.bulletkeyword',
                    fields=entry
                )
                serialized.append(formatted)
    result = json.dumps(serialized)
    for obj in serializers.deserialize('json', result):
        obj.save()
    print('Bullet analysis hook completed successfully')