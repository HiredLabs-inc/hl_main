# Resumationator helps tailor your resume to job posts.
#
# Copyright (C) 2022 Jeff Stock <jantonstock@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>


import collections
import nltk
from django.core import serializers

from cold_apply.static.scripts.resume_writer import vars
import json

# import time
# import matplotlib.pyplot as plt
import pandas as pd


# def fetch_base_data(filepath):
#     data = pd.read_csv(filepath, header=None)
#     data.columns = ['label', 'body_text']
#     # data['body_text_nostop'] = data['body_text'].apply(lambda x: clean_data(x.lower()))
#     return data


# def feature_text_length(filepath):
#     data = fetch_base_data(filepath)
#     data['body_len'] = data['body_text'].apply(lambda x: len(x) - x.count(' '))
#     return data


# def make_hist(filepath):
#     data = feature_text_length(filepath)
#     bins = np.linspace(2, 6000, 100)
#     pyplot.hist(data[data['label'] == 'nofit']['body_len'], bins, alpha=0.5, label='nofit')
#     pyplot.hist(data[data['label'] == 'fit']['body_len'], bins, alpha=0.5, label='fit')
#     pyplot.legend(loc='upper left')
#     pyplot.show()

# takes in a list of job descriptions
# def chart_token_freq(jd_set):
#     # print('Parsing verb stems...')
#     # time.sleep(2)
#     verbs = chart_prepper(jd_set, 'VERB')
#     verb_group_data = verbs[0]
#     verb_group_names = verbs[1]
#
#     # print('Parsing adjective stems...')
#     # time.sleep(2.0009)
#     adj = chart_prepper(jd_set, 'ADJ')
#     adj_group_data = adj[0]
#     adj_group_names = adj[1]
#
#     # print('Parsing noun stems...')
#     # time.sleep(2.0009)
#     nouns = chart_prepper(jd_set, 'NOUN')
#     noun_group_data = nouns[0]
#     noun_group_names = nouns[1]
#
#     # print('Finding the most impactful language...')
#     # time.sleep(2.3)
#     # print('Preparing vizualization...')
#     # time.sleep(3.4)
#
#     fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(10, 10))
#     fig.suptitle('Most Common Stems [top 20]')
#     ax1.barh(verb_group_names, verb_group_data)
#     ax1.invert_yaxis()
#     ax1.set_ylabel('Stems')
#     ax1.set_xlabel('Frequency')
#     ax1.set_title('Verbs')
#
#     ax2.barh(adj_group_names, adj_group_data)
#     ax2.invert_yaxis()
#     ax2.set_xlabel('Frequency')
#     ax2.set_title('Adjectives')
#
#     ax3.barh(noun_group_names, noun_group_data)
#     ax3.invert_yaxis()
#     ax3.set_xlabel('Frequency')
#     ax3.set_title('Nouns')
#     plt.show()
# TODO: Make this a class
def corpus_prepper(corpus: str) -> list:
    # jds = os.listdir(path=corpus) TODO: Make this a class attribute that can be passed from the web page
    jds = ['test_jd.txt']
    if len(jds) == 0:
        print('No job descriptions for corpus_prepper.')
        pass
    else:
        return [corpus + jd for jd in jds]


def tagger(text):
    output = {}
    for sentence in text:
        tokens = nltk.word_tokenize(sentence)
        tagged = nltk.pos_tag(tokens, tagset='universal')
        output.update(tagged)
    return output


def pos_finder(text: str, pos: str) -> dict:
    ps = nltk.PorterStemmer()
    tag_set = vars.pos_tags
    sentences = text.split('.')
    tagged_sents = tagger(sentences)
    stemmed_tokens = {}
    count = 0
    for token in tagged_sents:
        tag = tagged_sents[token]
        if tag in tag_set[pos]:
            count += 1
            stemmed_tokens[count] = ps.stem(token)

    return stemmed_tokens


def nonsense_filter(token_dict: dict) -> dict:
    fit_tokens = {}
    count = 0
    for d in token_dict:
        stem = token_dict[d]
        if stem not in vars.nonsense and len(stem) > 1:
            fit_tokens[count] = stem
            count += 1
    return fit_tokens


def data_grouper(token_set):
    group_data = []
    group_names = []
    for word in token_set:
        group_data.append(word[1])
        group_names.append(word[0])
        return group_data, group_names


def freq_ranker(token_set):
    counter = collections.defaultdict(int)
    for token in token_set:
        counter[token_set[token]] += 1
    ranked = sorted(counter.items(), key=lambda item: item[1], reverse=True)
    return ranked[:20]


def token_compiler(jd: str, pos: str) -> dict:
    jd_set = corpus_prepper(jd)
    all_tokens = {}
    count = 0
    for description in jd_set:
        tokens = pos_finder(description, pos)
        for t in tokens:
            all_tokens[count] = tokens[t]
            count += 1
    return all_tokens


def token_ranker(jd_set, pos):
    all_tokens = token_compiler(jd_set, pos)
    fit_tokens = nonsense_filter(all_tokens)
    common_tokens = freq_ranker(fit_tokens)
    ranked = data_grouper(common_tokens)
    return ranked


def bullet_strength_calculator(res_stems: list, jd_stems: list) -> int:
    count = 0
    for stem in res_stems:
        if stem in jd_stems:
            count += 1
    return count


def weigh(jd_keywords: object, bullet_keywords: object):
    weight = 0
    jd_unique = set()
    bullet_unique = set()
    for word in jd_keywords:
        bigram_singles = word.bigram.split(' ')
        bigram_1, bigram_2 = bigram_singles[0], bigram_singles[1]
        trigram_singles = word.trigram.split(' ')
        trigram_1, trigram_2, trigram_3 = trigram_singles[0], trigram_singles[1], trigram_singles[2]
        if word.unigram not in jd_unique:
            jd_unique.add(word.unigram)
        if bigram_1 not in jd_unique:
            jd_unique.add(bigram_1)
        if bigram_2 not in jd_unique:
            jd_unique.add(bigram_2)
        if trigram_1 not in jd_unique:
            jd_unique.add(trigram_1)
        if trigram_2 not in jd_unique:
            jd_unique.add(trigram_2)
        if trigram_3 not in jd_unique:
            jd_unique.add(trigram_3)

    for k_word in bullet_keywords:
        bigram_singles_2 = k_word.bigram.split(' ')
        bigram_3, bigram_4 = bigram_singles_2[0], bigram_singles_2[1]
        trigram_singles_2 = k_word.trigram.split(' ')
        trigram_4, trigram_5, trigram_6 = trigram_singles_2[0], trigram_singles_2[1], trigram_singles_2[2]
        if k_word.unigram not in bullet_unique:
            bullet_unique.add(k_word.unigram)
        if bigram_3 not in bullet_unique:
            bullet_unique.add(bigram_3)
        if bigram_4 not in bullet_unique:
            bullet_unique.add(bigram_4)
        if trigram_4 not in bullet_unique:
            bullet_unique.add(trigram_4)
        if trigram_5 not in bullet_unique:
            bullet_unique.add(trigram_6)
        if trigram_6 not in bullet_unique:
            bullet_unique.add(trigram_3)


    for word in bullet_unique:
        if word in jd_unique:
            weight += 1

    data = {
        'weight': [weight]
    }
    main_df = pd.DataFrame.from_dict(data)
    print('Weighting completed successfully')
    return main_df.to_json(orient='index')


def hook_after_weighting(task, position_id: int, participant_id: int, bullet_id: int):
    data = json.loads(task)
    serialized = list()
    for line in data:
        data[line]['position'] = position_id
        data[line]['participant'] = participant_id
        data[line]['bullet'] = bullet_id
        formatted = dict(
            model='cold_apply.weightedbullet',
            fields=data[line]
        )
        serialized.append(formatted)
    result = json.dumps(serialized)
    for obj in serializers.deserialize('json', result):
        obj.save()
    print('Weighting hook completed successfully')
