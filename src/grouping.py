import json
import pandas as pd
from pandas.core import indexers
from itertools import groupby
from collections import defaultdict


def group_blocks_ids(record_separation, block_separation):


    blocks_df = pd.DataFrame()
    for page in block_separation['pages']:
        for block in page['blocks']:
            blocks_df = pd.concat([blocks_df, pd.DataFrame([{
                "page" : page['page'],
                "block_id" : block['uid'],
                "y_start" : block['y_start'],
                "y_end" : block['y_end']
                }])])

    grouped = []

    for record in record_separation['records']:

        page_start, page_end = record['pages'][0]['page'], record['pages'][-1]['page']
        y_start, y_end = record['pages'][0]['y_start'], record['pages'][-1]['y_end']

        sub = blocks_df.loc[(blocks_df['page'] >= page_start) & (blocks_df['page']<=page_end)]
        sub = sub.loc[~((sub['page'] == page_start) & ( sub['y_start'] < y_start))]
        sub = sub.loc[~((sub['page'] == page_end) & ( sub['y_end'] > y_end))]

        grouped.append((record['record_id'], sub['block_id'].values))

    return grouped

def group_extarcted_blocks(groups, extracted):
    blocks_mapping = {}
    for i in groups:
        for bl in i[1]:
            blocks_mapping[bl] = i

    grouped = defaultdict(list)
    for block in extracted:
        record_id = blocks_mapping[block["uid"]][0]
        grouped[record_id].append(block)

    result = [{"record_id": record_id, "data": blocks} for record_id, blocks in grouped.items()]
    with open("test_grouping.json", "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))

def main(record_separation, block_separation, extracted):

    bl_uid = 1
    for page in block_separation['pages']:
        for block in page['blocks']:
            block['y_start'] = min([el['top'] for el in block['words']])
            block['y_end'] = max([el['bottom'] for el in block['words']])
            block['uid'] = bl_uid
            bl_uid += 1
    bl_uid = 1
    for block in extracted:
            block['uid'] = bl_uid
            bl_uid += 1

    groups = group_blocks_ids(record_separation, block_separation)
    group_extarcted_blocks(groups, extracted)


if __name__ == "__main__":
    with open("../data/id_10/pipeline/block_separation.json", "r") as f:
        block_sep = json.load(f)
    with open("../data/id_10/pipeline/record_separation.json", "r") as f:
        record_sep = json.load(f)

    with open("../data/id_10/pipeline/extracted.json", "r") as f:
        extr = json.load(f)

    main(record_sep, block_sep, extr)









