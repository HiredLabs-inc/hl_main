#!/usr/bin/python3

import json
import string
import pandas as pd
from django.core import serializers
from sklearn.feature_extraction.text import TfidfVectorizer
from cold_apply.models import KeywordAnalysis, Job, StopwordGroup



class Analyzer:
    def __init__(self, job_description: str, stopword_category: str):

        self.input_text = job_description.lower()
        self.unigrams = []
        self.bigrams = []
        self.trigrams = []
         # Load stopwords for the selected category
        try:
            group = StopwordGroup.objects.get(category=stopword_category)
            stopwords_str = group.words
            def normalize_stopword(word):
                return ''.join([c for c in word.lower() if c not in string.punctuation])
            self.stopwords = [normalize_stopword(w.strip()) for w in stopwords_str.split(',') if w.strip()]
        except StopwordGroup.DoesNotExist:
            self.stopwords = []
        print(f"STOPWORDS LOADED for category '{stopword_category}':", self.stopwords)

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
def analyze(job_description: str):
    # Instantiate analyzer with job description text
    words = job_description.split(' ')
    if len(words) < 5:
        job_description += ' '
        job_description *= 10

    categories = [
        "nltk english stopwords",
        "low value",
        "industry protected"
    ]
    results = {}
    for cat in categories:
        analyzer = Analyzer(job_description, stopword_category=cat)
        results[cat] = {
            'unigram': analyzer.find_keywords(1, 1),
            'bigram': analyzer.find_keywords(2, 2),
            'trigram': analyzer.find_keywords(3, 3)
        }
    return results

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