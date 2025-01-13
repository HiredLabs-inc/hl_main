import json

import pandas as pd
from django.core import serializers

from rates.static.scripts.rate_core.core_utils import bigStepper, levelStepper
import datetime


def recommend(level, zone, title, rate):
    zone_hash = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6}
    mid = bigStepper(level=level, zone=zone_hash[zone], rate=float(rate), title=title)
    high = round(mid * 1.1, 2)
    low = round(mid * .9, 2)
    rec = {
        'highest_rate': [high],
        'median_rate': [mid],
        'lowest_rate': [low],
    }
    main_df = pd.DataFrame.from_dict(rec)
    return main_df.to_json(orient='index')

def ref_rate_recommend(level, zone, title, rate):
    zone_hash = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6}
    mid = levelStepper(level=level, zone=zone_hash[zone], rate=float(rate), title=title)
    rec = {
        'median_rate': [mid],
    }
    return rec

def hook_after_recommendation(reco: object, req_id: int):
    data = json.loads(reco)
    serialized = list()
    for line in data:
        data[line]['rate_request'] = req_id
        formatted = dict(
            model='rates.rateresponse',
            fields=data[line]
        )
        serialized.append(formatted)
    result = json.dumps(serialized)
    for obj in serializers.deserialize('json', result):
        obj.save()
    print('Recommendation hook completed successfully')


if __name__ == '__main__':
    reco = recommend(
        level=int(input('Enter a level integer between 1 and 11:\n')),
        zone=input('Enter a zone letter A to F:\n'),
        title=input('Enter a title:\n'),
        rate=float(input('Enter a reference pay rate (lowest level in the most expensive zone): '))
    )

    spacer = '*' * 50
    cli_statement = f'\n{spacer}\nRecommended rate for a level {reco["level"]} {reco["title"]} in zone {reco["zone"]} is' \
                    f':\n\nhigh: {reco["high"]}\nmid: {reco["mid"]}\nlow: {reco["low"]}\n\nGenerated: {reco["now"]}\n{spacer}'

    print(cli_statement)
