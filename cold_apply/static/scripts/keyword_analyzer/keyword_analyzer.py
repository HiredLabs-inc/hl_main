#!/usr/bin/python3
# Main references:
# (1) localtools/resume_parser/static/scripts/resume_parser/parser.py)
# (2) TODO: Find resume parser project on external drive for reference

import json
import string

import nltk
import pandas as pd
from django.core import serializers


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

    def find_keywords(self):
        # TODO: Replace placeholders with real NLP shit (2)
        main_df = pd.DataFrame()
        # PLACEHOLDERS
        cleaned_words = self.parse()
        for word in cleaned_words:
            # Unigram placeholder
            if len(self.unigrams) < 20 and word not in self.unigrams:
                self.unigrams.append(word)
            # Bigram placeholder
            if cleaned_words.index(word) < len(cleaned_words) - 1:
                bigram = word + ' ' + cleaned_words[cleaned_words.index(word) + 1]
            else:
                bigram = f'{word} {word}'

            if len(self.bigrams) < 20 and bigram not in self.bigrams:
                self.bigrams.append(bigram)
            # Trigram placeholder
            if cleaned_words.index(word) < len(cleaned_words) - 2:
                trigram = word + ' ' + cleaned_words[cleaned_words.index(word) + 1] + ' ' + cleaned_words[
                    cleaned_words.index(word) + 2]
            else:
                trigram = f'{word} {word} {word}'

            if len(self.trigrams) < 20 and trigram not in self.trigrams:
                self.trigrams.append(trigram)


# Initialize analyzer
def analyze(job_description: str):
    # Instantiate analyzer with job description text
    analyzer = Analyzer(job_description)
    # Parse job description and set class uni-, bi- and trigram attributes
    analyzer.find_keywords()
    # turn class attributes into a json object
    data = {
        'unigram': analyzer.unigrams[:20],
        'bigram': analyzer.bigrams[:20],
        'trigram': analyzer.trigrams[:20]
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
