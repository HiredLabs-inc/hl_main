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


import json

import nltk
import pandas as pd
from django.core import serializers


def weigh(jd_keywords: object, bullet: object):
    weight = 0
    ps = nltk.PorterStemmer()
    jd_unique = set()
    bullet_stems = set()
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

    jd_stems = set()
    for word in jd_unique:
        jd_stems.add(ps.stem(word))

    for word in bullet.text.split(' '):
        bullet_stems.add(ps.stem(word))

    for stem in bullet_stems:
        if stem in jd_stems:
            weight += 1

    data = {
        'weight': [weight]
    }
    main_df = pd.DataFrame.from_dict(data)
    # print('Weighting completed successfully')
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
    return obj.object
    # print('Weighting hook completed successfully')
