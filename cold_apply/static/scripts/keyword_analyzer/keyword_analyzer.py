#!/usr/bin/python3
# Main references:
# (1) localtools/resume_parser/static/scripts/resume_parser/parser.py)
# (2) TODO: Find resume parser project on external drive for reference

import json
import string

import nltk
import pandas as pd
from django.core import serializers
from sklearn.feature_extraction.text import TfidfVectorizer


class Analyzer:
    def __init__(self, job_description: str):
        super(Analyzer).__init__()
        self.input_text = job_description.lower()
        self.unigrams = list()
        self.bigrams = list()
        self.trigrams = list()
        self.eng_stop_words = nltk.corpus.stopwords.words('english')
        self.stopwords = [
            'experience',
            'etc',
            'role',
            'candidate',
            'greenlight',
            'preferred',
            'qualifications',
            'weekly',
            'daily',
            'monthly',
            'quarterly',
            'key',
            'work',
            'dollar',
            'uber',
            'next',
            'com',
            'jan',
            'dec',
            'jun',
            '17',
            '15',
            'playstation',
            'new',
            'nextdoor',
            'across',
            'strong',
            'skills',
            'bosp',
            'stanford',
            'responsibilities',
            'within',
            'vpue',
            'job'

        ]
        self.cleaned_words = self.parse()

    def get_stops(self):
        for w in self.eng_stop_words:
            self.stopwords.append(w)

    def parse(self):
        # Remove punctuation
        text = ''.join([c for c in self.input_text if c not in string.punctuation])
        # Split description into words
        tokens = text.split()
        # Remove stopwords
        words = [word for word in tokens if word not in self.stopwords]
        # return cleaned data as a list of words
        return words

    def find_keywords(self, lower_bound, upper_bound):
        # TODO: Replace placeholders with real NLP shit (2)
        """
            takes a string, boundaries (upper and lower) for
            the ngram_range parameter of TfidfVectorizer
            returns list of the top 20 most important ngrams
            lower_bound = integer representing the lower bound of ngram_range
            upper_bound = integer representing the upper bound of ngram_range
            filepath_list = list of filepaths to job post text files

            """
        vectorizer = TfidfVectorizer(input='content', ngram_range=(lower_bound, upper_bound), stop_words=self.stopwords)
        X_tfidf = vectorizer.fit_transform([self.input_text])
        feature_names = vectorizer.get_feature_names_out()
        X_tfidf_df = pd.DataFrame(X_tfidf.toarray())
        X_tfidf_df.columns = feature_names
        X_tfidf_df.sort_values(by=X_tfidf_df.index[0], axis=1, inplace=True, ascending=False)
        top_twenty = X_tfidf_df.iloc[:, :20].columns.tolist()

        return top_twenty


# Initialize analyzer
def analyze(job_description: str):
    # Instantiate analyzer with job description text
    analyzer = Analyzer(job_description)
    # Update stopword list with Enlgish from NLTK + custom stopwords
    analyzer.get_stops()
    # Parse job description and set class uni-, bi- and trigram attributes
    analyzer.unigrams = analyzer.find_keywords(1, 1)
    analyzer.bigrams = analyzer.find_keywords(2, 2)
    analyzer.trigrams = analyzer.find_keywords(3, 3)
    # turn class attributes into a json object
    data = {
        'unigram': analyzer.unigrams,
        'bigram': analyzer.bigrams,
        'trigram': analyzer.trigrams,
    }
    main_df = pd.DataFrame.from_dict(data)
    return main_df.to_json(orient='index')


# Writes results to database
def hook_after_analysis(task, job_id: int):
    data = json.loads(task)
    serialized = list()
    for line in data:
        data[line]['job'] = job_id
        formatted = dict(
            model='cold_apply.keywordanalysis',
            fields=data[line]
        )
        serialized.append(formatted)
    result = json.dumps(serialized)
    for obj in serializers.deserialize('json', result):
        obj.save()
    print('Hook completed successfully')
