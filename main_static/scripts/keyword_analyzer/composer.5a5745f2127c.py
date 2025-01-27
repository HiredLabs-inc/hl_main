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

import nltk

from lang_processors.analyzer import pos_tagger
from handlers.file_parser import csv_to_list
from nltk.corpus import wordnet, treebank
from nltk.text import Text
from nltk import word_tokenize

def show_tree(sentence: str)-> str:
    t = treebank.parsed_sents('sentence')
    t.draw()

def synonymizer(word: str)-> set:
    synonyms = list()
    for syn in wordnet.synsets(word):
        for lem in syn.lemmas():
            synonyms.append(lem.name())
    return set(synonyms)

def create_text(example):
    tokens = word_tokenize(example[0])
    base = Text(tokens)
    text = base.generate()
    return text

# return only strong synonmys for a given verb
# def strong_syns(sentence):
#     verb = sentence.split(' ')[0]
#
#     # fetch strong verbs
#     strong_verb_path = './user_input/action_verbs.csv'
#     strong_verbs_list = csv_to_list(strong_verb_path)
#
#     synonmys = synonymizer(verb)
#     strong = [syn for syn in synonmys if syn in strong_verbs_list]
#     return strong
