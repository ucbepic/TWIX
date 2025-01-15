import key,extract,json,sys,csv,math,os
import numpy as np 
import key
import math
import time 
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import min_weight_full_bipartite_matching
root_path = extract.get_root_path()
sys.path.append(root_path)
from model import model 
from gurobipy import Model, GRB
model_name = 'gpt4o'
vision_model_name = 'gpt4vision'

metadata_rows = []

def add_metadata_row(row):
    metadata_rows.append(row)

def check_metadadta_row(row):
    for meta_row in metadata_rows:
        if(len(row) == len(meta_row)):
            match = 1
            for i in range(len(row)):
                pi = row[i]
                pj = meta_row[i]
                if(pi.lower() != pj.lower()):
                    match = 0
                    break
            if(match == 1):
                return 1
    return 0


def scan_folder(path, filter_file_type = '.json'):
    file_names = []
    for root, dirs, files in os.walk(path):
        for file in files:
            file_name = os.path.join(root, file)
            if('DS_Store' in file_name):
                continue
            if(filter_file_type not in file_name):
                continue
            file_names.append(file_name)
    return file_names


def read_string(file):
    data = ''
    with open(file, 'r') as file:
        # Iterate over each line in the file
        for line in file:
            # Print the line (you can replace this with other processing logic)
            data += (line.strip()) 
    return data

def read_file(file):
    data = []
    with open(file, 'r') as file:
        # Iterate over each line in the file
        for line in file:
            # Print the line (you can replace this with other processing logic)
            data.append(line.strip()) 
    return data

def read_json(path):
    with open(path, 'r') as file:
        data = json.load(file)
    return data

def template_learn_input_gen(phrases, predict_labels, extra_phrase_num = 30):
    input = []
    cnt = {}
    satisfied = 0
    cnts = {}
    #goal: ensure that input contains each predict label at least twice
    for i in range(len(phrases)):
        p = phrases[i]
        input.append(p)
        if(p in predict_labels):
            #print(p)
            if(p in cnt):
                cnt[p] += 1
            else:
                cnt[p] = 0
            if(cnt[p] >= 1 and p not in cnts):#ensure each key is counted once
                cnts[p] = 1
                satisfied += 1
            if(satisfied == len(predict_labels)): #each predict label occurs in input at least twice
                c = 0
                for j in range(i+1,len(phrases)):
                    input.append(phrases[j])
                    c += 1
                    if(c > extra_phrase_num):
                        break
                return input
    print('There does not exist an input such that every predict key exists at least twice.')
    return []


def get_bb_path(extracted_file):
    file = extracted_file.replace('.txt','.json')
    return file 


def key_val_extraction(pv, predict_labels):
    #print(pv, predict_labels)
    kvs = []
    i = 0
    while i < len(pv):
        p = pv[i][0]
        if (p in predict_labels and i+1<len(pv) and pv[i+1][0] not in predict_labels):
            kvs.append((p,pv[i+1][0]))
            i += 2
        elif(p in predict_labels and i+1<len(pv) and pv[i+1][0] in predict_labels):
            kvs.append((p,'missing'))
            i += 1
        elif(p in predict_labels and i == len(pv)-1):
            kvs.append((p,'missing'))
            i += 1
        elif(p not in predict_labels):
            i += 1
        else:
            i += 1

    return kvs


def min_distance(bb1,bb2):
    # min(current_bbox[0], word['x0']),
    # min(current_bbox[1], word['top']),
    # max(current_bbox[2], word['x1']),
    # max(current_bbox[3], word['bottom'])
    lx = [abs(bb1[0]-bb2[0]), abs(bb1[0]-bb2[2]),abs(bb1[2]-bb2[0]),abs(bb1[2]-bb2[2])]
    ly = [abs(bb1[1]-bb2[1]), abs(bb1[1]-bb2[3]),abs(bb1[3]-bb2[1]),abs(bb1[3]-bb2[3])]
    x_min = min(lx)
    y_min = min(ly)
    return max(x_min,y_min)

    

def get_bblist_per_record(record_appearance, phrases_bb, phrases):
    #phrases: list of phrases 
    #phrases_bb: phrase -> bounding box of all appearances of this phrase 
    #record_appearance: phrase->the number of appearances of p so far 
    #phrase_boundingbox: a list of tuple. Each tuple:  (phrase, bounding box) for current record 
    phrase_boundingbox = []
    appear = {}
    record = {}
    for p in phrases:
        c = phrases.count(p)
        cur = record_appearance[p]
        if(p in phrases_bb):
            lst = phrases_bb[p][cur: cur + c]
            if(p not in appear):
                appear[p] = 0
                record[p] = cur + c
            else:
                appear[p] = appear[p] + 1

            bb = lst[appear[p]]
            phrase_boundingbox.append((p,bb))
    for p in phrases:
        if(p in phrases_bb):
            record_appearance[p] = record[p]
            
    return phrase_boundingbox

def get_bb_per_record(record_appearance, phrases_bb, phrases):
    #phrases: phrase -> a list of bounding box for all records 
    #record_appearance: phrase p->the number of appearances of p so far 
    #output: a list of tuple. Each tuple:  (phrase, bounding box) for current record 
    pv = []
    non_dul_phrases = list(set(phrases))#remove duplicated phrases 
    for p in non_dul_phrases:
        c = phrases.count(p)
        if(p not in pv and p in phrases_bb):
            cur = record_appearance[p]
            lst = phrases_bb[p][cur: cur + c]
            #create tuple instances 
            for bb in lst:
                pv.append((p,bb))
            record_appearance[p] = cur + c
    return record_appearance, pv

def get_horizontal_mid(bb):
    return (bb[0] + bb[2])/2

def find_closest_value(val, lst):
    if(len(lst) == 0):
        return -1
    # Use a list comprehension to calculate the absolute differences
    closest_val = min(lst, key=lambda x: abs(x - val))
    return closest_val

def is_inclusive(b1,b2):
    #input: b1 and b2 are bounding box of two phrases 
    if(b1[2] < b2[0]):
        return 0
    if(b2[2] < b1[0]):
        return 0
    return 1

def is_aligned(b1,b2):
    if(b1[1] > b2[3]):
        return 0
    if(b1[3] < b2[1]):
        return 0
    return 1

def is_overlap_vertically(b1,b2):
    if(b1[2] < b2[0]):
        return 0
    if(b1[0] > b2[2]):
        return 0
    return 1


def h_distance(bb1, bb2):
    bb1_avg = (bb1[0]+bb1[2])/2
    bb2_avg = (bb2[0]+bb2[2])/2 
    return abs(bb1_avg - bb2_avg)

def key_val_mp(key_row, val_row):
    kv_mp = {}
    #print(val_row)
    #for each key, search its cloest and overlapping value 
    for item in key_row:
        key = item[0]
        keyb = item[1]
        hd = 10000000
        t_val = 'missing'
        for item in val_row:
            val = item[0]
            valb = item[1]
            if(is_overlap_vertically(keyb, valb) == 0):
                continue 
            if(h_distance(keyb,valb) < hd):
                hd = h_distance(keyb, valb)
                t_val = val
        kv_mp[key] = t_val
    #print(kv_mp)
    return kv_mp



def table_extraction_top_down(row_mp, kid, vid):
    key_row = row_mp[kid[0]]
    val_rows = []
    kvs = []
    rows = []# list of list 
    keys = []
    for (key,bb) in key_row:
        keys.append(key)
    #print(key_row)
    for id in vid:
        #print(id)
        val_rows.append(row_mp[id])
        #print(row_mp[id])
    for val_row in val_rows:
        kv = key_val_mp(key_row, val_row)
        #print(kv)
        kvs.append(kv)
    #clean the tabular format
    for kv in kvs:
        row = []
        for (key,bb) in key_row:
            row.append(kv[key])
        rows.append(row)
    #print(rows)
    return keys, rows


def format_dict(dict):
    d = {}
    for k,v in dict.items():
        d[k.lower()] = v
    return d

def write_result(results,path):
    with open(path, 'w', newline='') as file:
        # Write each row to the CSV file
        for row in results:
            key = row[0]
            val = row[1]
            page = 1.0
            if(',' in val):
                val = val.replace(',','')
            out = key +','+val +','+str(page)
            #print(out)
            file.write(out + '\n')

def is_same_row(b1,b2):
    #b2 should be in the right side of b1
    if(b2[0] < b1[0]):
        return 0
    # b1 and b2 should overlap in y
    if(b1[3] < b2[1] or b1[1] > b2[3]):
        return 0
    return 1



def row_aligned(row1, row2):
    #check if there exist a phrase in row2 that overlapps with more than 2 phrases in row1
    
    id1 = 1 #id in row 1
    id2 = 0 #id in row 2
    match = 0
    #a value should not overlap with two keys
    while(id1 < len(row1) and id2 < len(row2)):
        if(is_overlap_vertically(row2[id2][1], row1[id1][1]) == 1 and is_overlap_vertically(row2[id2][1], row1[id1-1][1]) == 1):
            #print(row1[id1], row1[id1-1], row2[id2])
            return 0
        if(row1[id1][1][2] < row2[id2][1][2]):
            id1 += 1
        else:
            id2 += 1
    #a key should not overlap with two values: the reason is that some keys are seperated by a large phrase and thus the bounding box for a key might be fully accurate (larger than original) 
    #row1: key, row2: val
    # id1 = 0
    # id2 = 1
    # while(id1 < len(row1) and id2 < len(row2)):
    #     if(is_overlap_vertically(row1[id1][1], row2[id2][1]) == 1 and is_overlap_vertically(row1[id1][1], row2[id2-1][1]) == 1):
    #         return 0
    #     #print(row1[id1][1][2], row2[id2][1][2])
    #     if(row1[id1][1][2] < row2[id2][1][2]):
    #         id1 += 1
    #     else:
    #         id2 += 1

    #write the percetage of keys that have the correspoinding unique value mapping

    #check if there exist a phrase in row2 that does not overlapps with any of val in row1 - this is not robust: if there exist one phrase that violates this condition, then this row would be not correct 
    
    # for (p2,bb2) in row2:
    #     valid = 0
    #     for (p1,bb1) in row1:
    #         if(is_overlap_vertically(bb2,bb1) == 1):
    #             valid = 1
    #             break
    #     if(valid == 0):
    #         return 0
    return 1
    
def block_decider(rls):
    blk = {}#store the community of all rows belonging to the same block: bid -> a list of row id 
    blk_id = {}#store the name per block: bid-> name of block
    bid = 0
    nearest_key_bid = 0
    kv_bid = -1 #all kvs can be put into one block
    for id, label in rls.items():
        if(label == 'key'):
            bid += 1
            blk[bid] = []
            blk[bid].append(id)
            blk_id[bid] = 'table'
            nearest_key_bid = bid
        elif(label == 'val' and nearest_key_bid > 0):
            blk[nearest_key_bid].append(id)
        elif(label == 'kv'):#start a new block for kv
            if(kv_bid == -1):
                bid += 1
                kv_bid = bid
                blk[kv_bid] = []
            blk[kv_bid].append(id)
            blk_id[kv_bid] = 'kv'
    #block smooth for kv 
    #impute all the undefined row inside the kv block to be kv 
    for bid, name in blk_id.items():
        if(name == 'kv'):
            #print(blk[bid])
            new_row = []
            l = blk[bid][0]
            r = blk[bid][len(blk[bid])-1]
            for i in range(l,r+1):
                new_row.append(i)
            blk[bid] = new_row
            #print(blk[bid])
    return blk, blk_id

def write_json(out, path):
    with open(path, 'w') as json_file:
        json.dump(out, json_file, indent=4)

def create_row_representations(phrases, phrases_bb):
    record_appearance = {}
    for p in phrases:
        record_appearance[p] = 0
    #print(phrases_bb)
    phrase_boundingbox = get_bblist_per_record(record_appearance, phrases_bb, phrases)

    #print(phrase_boundingbox)
    #create row representations 
    #row_mp: row_id -> a list of (phrase, bb) in the current row
    row_mp = seperate_rows(phrase_boundingbox)

    return row_mp


def get_metadata(image_paths):
    #prompt = 'The given two images have common headers and footers in the top and bottem part of the image. Return only the raw headers and footers. Do not return other phrases. Do not add any explanations. '
    prompt = 'The given two images have common headers and footers in the top and bottem part of the image. Extract only the common raw headers and footers from the given two images. Exclude all other phrases. Do not include explanations. Seperate headers and footers by |'
    
    response = model(vision_model_name,prompt,image_paths)
    #phrases = [phrase.strip() for phrase in response.split('|')]
    return response 

def check_phrase_in_headers_or_footers(headers_footers: str, given_phrase: str):

    # Check if the given phrase is a substring of any phrase in the list
    for phrase in headers_footers:
        if given_phrase.lower() in phrase.lower():
            return 1

    return 0


def is_row_headers_or_footers(row, metadata):
    #this can be improved by row id in a page: headers and footers are close to boundary of a page: to do later 
    contained = 0
    for p in row:
        contained += check_phrase_in_headers_or_footers(metadata, p)
    
    if(contained/len(row) >= 0.7):
        return is_row_headers_or_footers_LLMs(row, metadata)
    return 0

def is_row_headers_or_footers_LLMs(row, metadata):

    #print('call LLMs for header detection...')

    instruction = 'Given the headers: ' + ','.join(metadata) + '. Decide whether the following row is a header:' + ','.join(row) + '. Return only yes or no. Do not add explanations. Note that a header row does not need to be exactly a substring of the given headers, and it is allowed to have extra phrases. It needs to be semantically a header. '  
    prompt = (instruction,'')
    response = model(model_name,prompt)
    print(instruction)
    print(response)
    if('yes' in response.lower()):
        return 1
    return 0


def is_metadata(meta, val):
    if(val not in meta):
        return 0
    # Initialize the list to store the indices
    indices = []
    start = 0

    # Loop to find all occurrences of the substring
    while True:
        index = meta.find(val, start)
        if index == -1:
            break
        indices.append(index)
        start = index + 1

    for i in indices:
        l = i-1
        r = i+len(val)
        f1 = 0
        f2 = 0
        if(l>=0 and (meta[l] == ' ' or meta[l] == '\n' or meta[l] == ':')):
            f1 = 1
        if(r<len(meta) and (meta[r] == ' ' or meta[r] == '\n' or meta[r] == ':')):
            f2 = 1
        if(l<0):
            f1 = 1
        if(r == len(meta)):
            f2 = 1
        if(f1 == 1 and f2 == 1):
            return 1
    return 0

def refine_sample(row_mp):
    #drop last row to account for the extra k phrases as the last row can be bad 
    new_mp = {}
    for id in range(len(row_mp)-1):
        new_mp[id] = row_mp[id]
    return new_mp

def mix_pattern_extract_pipeline(phrases_bb, predict_labels, raw_phrases, extraction_path, template_path, metadata):
    print('fields...')
    print(predict_labels)
    # print('raw phrases...')
    # print(raw_phrases)
    #get minimal set of phrases to learn template 
    phrases = template_learn_input_gen(raw_phrases, predict_labels)
    # print('phrases')
    # print(phrases)
    row_mp = create_row_representations(phrases, phrases_bb)
    print(len(row_mp))
    row_mp = refine_sample(row_mp)
    print(len(row_mp))
    #print_row(row_mp)

    template = ILP_extract(predict_labels, row_mp, template_path, metadata)
    
    print('Metadata rows...')
    print(metadata_rows)
    #seperate records based on template 
    print("Record seperation starts...")
    complete_row_mp = create_row_representations(raw_phrases, phrases_bb)
    records = record_seperation(template, complete_row_mp)

    # print('Records...')
    # for record in records:
    #     print(record)

    #seperate data blocks within each record based on template 
    print('Block Seperation starts...')
    blocks = block_seperation_pipeline(template, records, complete_row_mp, metadata)

    #data extraction within each data block based on template 
    print('Data extraction starts...')
    extraction_objects = data_extraction(records, blocks, complete_row_mp, template)

    write_json(extraction_objects, extraction_path)


def record_seperation(template, row_mp):
    row_id = 0
    boundary_fields = []

    #decide boundary_fields
    while(row_id < len(row_mp)):
        #get phrases in current row 
        row_phrases = []
        for item in row_mp[row_id]:
            row_phrases.append(item[0])
        
        if(visit_node(template[0], row_phrases) == 1):
            boundary_fields = set(template[0]['fields']).intersection(row_phrases)
            break
        row_id += 1
           
    #record seperation 
    first_record = 1
    row_id = 0
    records = []
    record = []

    while(row_id < len(row_mp)):
        #get phrases in current row 
        row_phrases = []
        for item in row_mp[row_id]:
            row_phrases.append(item[0])

        #visit the first node twice implying a new record 
        if(is_contained(boundary_fields, row_phrases) == 1):
            if(first_record == 1): #this is the first record 
                first_record = 0
            else:#another new record 
                records.append(record)
                record = []

        record.append(row_id)
        row_id += 1
    
    records.append(record) #add last record 

    return records        
         
def is_contained(boundary_fields, phrases):
    for p in boundary_fields:
        if (p not in phrases):
            return 0
    return 1


def visit_node(node, row):
    fields = node['fields']
    type = node['type']
    if(type == 'table'):
        for p in row:
            if(p not in fields):
                return 0
        return 1
    if(type == 'kv'):
        for p in row: 
            if(p in fields):
                return 1
        return 0 

def ILP_extract(predict_keys, row_mp, template_path, metadata):
    #row_mp: row_id -> a list of (phrase, bb) in the current row
    row_labels = get_row_probabilities(predict_keys, row_mp, metadata)

    #pre-compute all C-alignments  
    row_align = {}
    for id1 in range(len(row_mp)):
        for id2 in range(id1+1, len(row_mp)):
            #print(row_labels[id1])
            if(id1 == 3):
                c=1
            if(row_labels[id1]['K'] >= 1):#only spend resources to align with key rows to speed up execution 
                c = C_alignment(row_mp, id1, id2)
            else:
                c = C_alignment_no_LLM(row_mp, id1, id2)
            if(row_labels[id1]['M'] >= 1):
                #print(id1)
                c = 0
            if(row_labels[id1]['V'] >= 1):
                c = 0

            row_align[(id1,id2)] = c
            row_align[(id2,id1)] = c

    print(row_align[(3,4)])
    #LP formulation to learn row label assignment
    print('initial row labels and probs:')
    print_row_labels(row_mp, row_labels)

    row_pred_labels = ILP_formulation(row_mp, row_labels, row_align)

    print('labels after ILP:')
    print(row_pred_labels)
    #seperate data blocks based on row labeling
    blk, blk_type = block_seperation(row_pred_labels, row_align)

    print(blk)
    print(blk_type)

    #learn template based on the data blocks 
    nodes = template_learn(blk, blk_type, row_mp)
    write_template(nodes, template_path)

    return nodes

def write_template(nodes,path):
    template = {}
    for i in range(len(nodes)):
        node = nodes[i]
        name = 'node'+str(i)
        template[name] = node
    write_json(template,path)

def template_learn(blk, blk_type, row_mp):
    #blk: bid -> a list of row id
    #blk_type: bid -> type of block 
    #row_mp: row_id -> a list of (phrase, bb) in the current row
    nodes = []#a list of node_instance which is a dict with node_fields, node_child, node_type
    #node_child = -1 denote a leaf

    #first pass: create all nodes using blk, based on reading order and deduplicate blk

    for bid, type in blk_type.items():
        node = {}
        if(type == 'table'):
            node['type'] = type
            #get fields
            field_row_id = blk[bid][0]
            fields = []
            for item in row_mp[field_row_id]:
                fields.append(item[0])
            node['fields'] = fields
            node['child'] = -1 
            node['bid'] = bid

        elif(type == 'kv'):
            node['type'] = type
            #get all phrases in current kv block
            phrases = []
            for row_id in blk[bid]:
                for item in row_mp[row_id]:
                    phrases.append(item[0])
            #get fields by LLMs 
            response = key.phrase_filter_LLMs(phrases)
            fields = key.clean_phrases(response, phrases)
            node['fields'] = fields
            node['child'] = -1 
            node['bid'] = bid
        else: #metadata type
            continue

        #decide if current node is duplicated with the first node 
        if(len(nodes) > 0 and nodes[0]['fields'] == fields and nodes[0]['type'] == type):
           break 

        if(len(fields) == 0):#prevent from adding an empty node 
            continue
        
        duplicate = 0
        for n in nodes:
            if(n['fields'] == fields and n['type'] == type):
                duplicate = 1
                break
        if(duplicate == 1):
            continue
        nodes.append(node)

    #second pass: add edges 
    for i in range(len(nodes)):
        for j in range(i+1,len(nodes)):
            bid_i = nodes[i]['bid']
            bid_j = nodes[j]['bid']
            rows_i = blk[bid_i]
            rows_j = blk[bid_j]
            print(rows_i,rows_j)
            if(rows_i[-1] > rows_j[0]):#data blocks overlapping
                nodes[i]['child'] = j

    for node in nodes:
        print(node)
    return nodes



def ILP_formulation(row_mp, row_labels, Calign):
    model = Model("RT")
    #model.setParam('OutputFlag', 0)
    
    # create variables 
    # for each row, create four variables 
    vars = {} #row_id -> list of variables 
    for row_id, row in row_mp.items():
        var = []
        var_K = 'yK' + str(row_id)
        yk = model.addVar(vtype=GRB.INTEGER, name=var_K)
        var.append(yk)

        var_V = 'yV' + str(row_id)
        yV = model.addVar(vtype=GRB.INTEGER, name=var_V)
        var.append(yV)

        var_KV = 'yKV' + str(row_id)
        yKV = model.addVar(vtype=GRB.INTEGER, name=var_KV)
        var.append(yKV)

        var_M = 'yM' + str(row_id)
        yM = model.addVar(vtype=GRB.INTEGER, name=var_M)
        var.append(yM)

        vars[row_id] = var
    
    #add constraint 1: for each row, the sum of four variables is 1
    for row_id, var in vars.items():
        model.addConstr(var[0] + var[1] + var[2] + var[3] == 1, "SumOnePerRow")

    #add constraint 2: validity of key row
    for row_id, var in vars.items():
        operand = 0
        for j in range(row_id+1, len(vars)):
            operand += (Calign[(row_id,j)]*vars[j][1])
        model.addConstr(var[0] <= operand, "KeyValidity")

    #add constraint 3: validity of value row 
    for row_id, var in vars.items():
        operand = 0
        for j in range(0, row_id):
            operand += (Calign[(row_id,j)]*vars[j][0])
        model.addConstr(var[1] <= operand, "ValueValidity")

    #add optimization function
    log_prob = 0
    for row_id, var in vars.items():
        prob = var[0]*math.log(row_labels[row_id]['K'])
        prob += var[1]*math.log(row_labels[row_id]['V'])
        prob += var[2]*math.log(row_labels[row_id]['KV'])
        prob += var[3]*math.log(row_labels[row_id]['M'])
        log_prob += prob
    model.setObjective(log_prob, GRB.MAXIMIZE)
    
    # Optimize the model
    model.optimize()

    # get the predictions
    row_pred_labels = {}
    if model.status == GRB.OPTIMAL:
        label = ''
        for row_id, var in vars.items():
            if(var[0].x == 1):
                label = 'K'
            elif(var[1].x == 1):
                label = 'V'
            elif(var[2].x == 1):
                label = 'KV'
            elif(var[3].x == 1):
                label = 'M'
            row_pred_labels[row_id] = label
    
    return row_pred_labels

def block_seperation(rls, row_align):
    blk = {}#store the community of all rows belonging to the same block: bid -> a list of row id 
    blk_type = {}#store the name per block: bid-> type of block
    bid = 0
    row_2_blk = {} #row id -> blk type

    #merge consecutive kv pairs into one kv block 

    for id, label in rls.items():
        if(label == 'K'):
            blk[bid] = []
            blk[bid].append(id)
            blk_type[bid] = 'table'
            row_2_blk[id] = bid
            bid += 1
        elif(label == 'V'):
            i = id - 1
            while(i >= 0):#find the cloest aligned key row of row with index id 
                if(rls[i] == 'K' and row_align[(i, id)] == 1):
                    key_blk_id = row_2_blk[i]
                    blk[key_blk_id].append(id)
                    break
                i -= 1
        elif(label == 'KV'):
            if(id - 1 >= 0 and rls[id-1] != 'KV'):
                blk[bid] = []
            blk[bid].append(id)
            blk_type[bid] = 'kv'
            if(id + 1 < len(rls) and (rls[id+1] == 'K' or rls[id+1] == 'V')):#if next row is K or V, create a new block
                bid += 1


    for bid, name in blk_type.items():
        #if a table block only has one row, change it to be M
        if(name == 'table'):
            if(len(blk[bid]) == 1):
                blk_type[bid] = 'metadata'
    return blk, blk_type


def row_label_gen_template(record, row_mp, template, metadata):
    rls = []#list of row labels per row
    row_node_mp = {}#row_id -> node_id generates this row: only store for row with label 'K', the row_id here should be relative row_id, starting from zero 
    base_row_id = record[0]  
    for row_id in record:
        row_phrases = []
        for item in row_mp[row_id]:
            row_phrases.append(item[0])
        
        if(check_metadadta_row(row_phrases) == 1):
            label = 'M'
        else:
            if(is_row_headers_or_footers(row_phrases, metadata) == 1): 
                label = 'M'
            else:
                label = ''
                for i in range(len(template)):
                    node = template[i]
                    if(visit_node(node, row_phrases) == 1):
                        if(node['type'] == 'table'):
                            label = 'K'
                            row_node_mp[row_id-base_row_id] = i
                        else:
                            label = 'KV'
                        break
                if(label == ''):
                    label = 'V'
        rls.append(label)
    return rls, row_node_mp
            
def row_align_gen_template(row_mp, record):
    row_align = {}
    for i in range(len(record)):
        for j in range(i+1, len(record)):
            id1 = record[i]
            id2 = record[j]
            c = C_alignment_no_LLM(row_mp, id1, id2)
            row_align[(id1,id2)] = c
            row_align[(id2,id1)] = c
    return row_align
        

def block_seperation_pipeline(template, records, row_mp, metadata):
    blocks = {}#record id -> (blk, blk_type) 
    for i in range(len(records)):
        record = records[i]
        rls, row_node_mp = row_label_gen_template(record, row_mp, template, metadata)
        # print('row labels...')
        # print(i,rls)
        # print(record)
        # print(row_mp[record[0]])
        row_align = row_align_gen_template(row_mp, record)
        # print('row align...')
        # print(row_align)
        blk, blk_type = block_seperation_based_on_template(rls, row_align, row_node_mp, template, record)
        # print(blk)
        # print(blk_type)
        blocks[i] = (blk, blk_type)
        # if(i >= 1):
        #     break
    return blocks


def block_seperation_based_on_template(rls, row_align, row_node_mp, template, record):
    #row_align stores the global record id and rls stores the relative record id
    record_delta = record[0]
    print(record_delta)
    # print('row_node_mp:')
    # print(row_node_mp)
    #rls:list of row labels
    blk = {}#bid -> a list of row id belonging to the same block 
    blk_type = {}#store the name per block: bid-> type of block
    bid = 0
    row_2_blk = {} #row id -> blk type

    #merge consecutive kv pairs into one kv block 

    for id in range(len(rls)):
        label = rls[id]
        if(label == 'K'):
            blk[bid] = []
            blk[bid].append(id)
            blk_type[bid] = 'table'
            row_2_blk[id] = bid
            bid += 1
        elif(label == 'V'):
            i = id - 1
            first_key = 0
            updated = 0
            while(i >= 0):#find the cloest aligned key row of row with index id 
                if(rls[i] == 'K'):
                    is_leaf = template[row_node_mp[i]]['child']
                    if(row_align[(i+record_delta, id+record_delta)] == 1):
                        if((is_leaf == -1 and first_key == 0) or (is_leaf != -1)):  
                            key_blk_id = row_2_blk[i]
                            blk[key_blk_id].append(id)
                            updated = 1
                            break
                    first_key = 1
                i -= 1
            if(updated == 0):#V row is not aligned with any candidate key row, set to be M
                label = 'M'
        elif(label == 'KV'):
            if(id - 1 >= 0 and rls[id-1] != 'KV'):
                blk[bid] = []
            blk[bid].append(id)
            blk_type[bid] = 'kv'
            if(id + 1 < len(rls) and (rls[id+1] == 'K' or rls[id+1] == 'V')):#if next row is K or V, create a new block
                bid += 1

    return blk, blk_type

def location_alignment(row_mp, id1, id2):
    return row_aligned(row_mp[id1], row_mp[id2]) 


def get_KV_scores(pairs):
    #construct prompts to LLMs
    instruction = 'Given a list of phrase pairs as (phrase1, phrase 2), for each pair of phrase, if two phrases are a key-value pair, return yes. Otherwise, return no. Do not add any explanations, only return yes or no for each phrase pair.'
    context = ", ".join(f"({repr(key)}, {repr(value)})" for key, value in pairs)
    prompt = (instruction,context)
    response = model(model_name,prompt)
    pos = response.lower().count('yes')

    return pos 

def semantic_alignment(row_mp, id1, id2):
    pairs = []
    for cell1 in row_mp[id1]:
        val1 = cell1[0]
        bb1 = cell1[1]
        for cell2 in row_mp[id2]:
            val2 = cell2[0]
            bb2 = cell2[1]
            if(is_overlap_vertically(bb1,bb2) == 1):
                pairs.append((val1,val2))
                break
    
    pos = get_KV_scores(pairs)
    if(len(pairs) == 0):
        return 0
    return pos/len(pairs)

def C_alignment_no_LLM(row_mp, id1, id2): #comprehensive alignment
    #print(id1,id2)
    l_score = location_alignment(row_mp, id1, id2)
    return l_score

def C_alignment(row_mp, id1, id2): #comprehensive alignment
    #print(id1,id2)
    l_score = location_alignment(row_mp, id1, id2)
    if(l_score == 1):
        len1 = len(row_mp[id1])
        len2 = len(row_mp[id2])
        if(len2 > len1/2):
            return 1
        else:
            print('LLM is called...')
            print(id1,id2)
            s_score = semantic_alignment(row_mp, id1, id2)
            if(s_score > 0.5):
                return 1
            return 0
    return 0
    # else:
    #     s_score = semantic_alignment(row_mp, id1, id2)
    #     if(s_score > 0.5):
    #         return 1
    #     return 0

def seperate_rows(pv):
    p_pre = pv[0][0]
    bb_pre = pv[0][1]
    row_id = 0
    row_mp = {} #row_id -> a list of (phrase, bb) in the current row, now the last bit in bb is the page number 
    #page_2_row = {} #page -> a list of row_id
    row_mp[row_id] = []
    row_mp[row_id].append((p_pre, bb_pre))
    for i in range(1, len(pv)):
        #create page_2_row map
        #page_number = bb_pre[4]
        # if(page_number not in page_2_row):
        #     page_2_row[page_number] = [row_id]
        # else:
        #     if(row_id not in page_2_row[page_number]):
        #         page_2_row[page_number].append(row_id)

        p = pv[i][0]
        bb = pv[i][1]
        if(is_same_row(bb_pre,bb) == 0):
            row_id += 1
            row_mp[row_id] = []
        row_mp[row_id].append((p, bb))
        p_pre = p
        bb_pre = bb

    return row_mp

def get_row_probabilities(predict_keys, row_mp, metadata):
    #input: a list of tuple. Each tuple:  (phrase, bounding box) for current record

    #for each row, compute the probability per label
    row_labels = {} #row_id -> label, label is also a dict: label instance -> probability 
    for row_id, row in row_mp.items():
        row_labels[row_id] = row_label_prediction(row, predict_keys, metadata)

    labels = row_label_LLM_refine(row_labels, row_mp)
    #print_rows(row_mp, labels)
    
    return labels

def get_LLM_row_score(row_id, row_mp):
    #get a list of phrases in this row 
    phrases = []
    for item in row_mp[row_id]:
        phrases.append(item[0])
    
    print(phrases)
    #get the predicted keys in this row 
    response = key.phrase_filter_LLMs(phrases)
    fields = key.clean_phrases(response, phrases) 
    print(fields)
    field_score = len(fields)/len(phrases)
    value_score = 1-field_score
    #estimate KV socres, first construct KV pairs
    kv_pairs = []#list of (key,value)
    p_pre = phrases[0]
    cnt = 0
    for i in range(1,len(phrases)):
        p = phrases[i]
        if(p_pre in fields and p in fields):
            cnt += 1
            continue
        if(p_pre in fields and p not in fields):
            kv_pairs.append((p_pre,p))
        p_pre = p 
    kv_scores = get_KV_scores(kv_pairs)
    kv_score = (kv_scores + cnt)/ (len(kv_pairs) + cnt)

    return field_score, value_score, kv_score


def row_label_LLM_refine(row_labels, row_mp):
    #for uncertain rows, use LLMs to adjust the weights
    labels = {}

    #get initial labels 
    row_tag = {}
    for row_id, label in row_labels.items():

        if(label['M'] == 1):
            row_tag[row_id] = 'M'
            labels[row_id] = label
            continue
        
        row_tag[row_id] = 'uncertain'
        #print(label['K'],label['V'],label['KV'])
        if(label['K'] == label['V'] and label['K'] > label['KV']):
            row_tag[row_id] = 'uncertain'
        elif(label['V'] == label['KV'] and label['V'] > label['K']):
            row_tag[row_id] = 'uncertain'
        elif(label['K'] == label['KV'] and label['K'] > label['V']): 
            row_tag[row_id] = 'uncertain'
        
        else:
            if(label['K'] > label['V'] and label['K'] > label['KV']):
                row_tag[row_id] = 'K'
            elif(label['V'] > label['K'] and label['V'] > label['KV']):
                row_tag[row_id] = 'V'
            elif(label['KV'] > label['K'] and label['KV'] > label['V']):
                row_tag[row_id] = 'KV'

    #adjust probabilities for uncertain rows
    delta = 0.001
    for row_id, label in row_labels.items():
        if(row_id not in row_tag):
            continue
        if(row_tag[row_id] != 'uncertain'):
            labels[row_id] = row_labels[row_id]
            continue
        if(label['K'] == label['V']):
            if(check_validity_per_row('K',row_id, row_tag, row_mp) == 1):
                label['K'] += delta
            else:
                label['V'] += delta
        if(label['K'] == label['KV']):
            if(check_validity_per_row('K',row_id, row_tag, row_mp) == 1):
                label['K'] += delta
            else:
                label['KV'] += delta
        if(label['V'] == label['KV']):
            if(check_validity_per_row('V',row_id, row_tag, row_mp) == 1):
                label['V'] += delta
            else:
                label['KV'] += delta
        labels[row_id] = label

    return labels

def check_validity_per_row(label, row_id, row_tag, row_mp):
    if(label == 'K'):
        i = row_id + 1
        while(i < len(row_tag)):
            if(row_tag[i] == 'K'):#apply locality 
                return 0
            if(row_tag[i] == 'V' and C_alignment_no_LLM(row_mp,row_id,i) == 1):
                if(semantic_alignment(row_mp, row_id, i) > 0.5):
                    return 1
                return 0
            i += 1
        return 0
    if(label == 'V'):
        i = row_id - 1
        while(i >= 0):
            if(row_tag[i] == 'K' and C_alignment_no_LLM(row_mp,row_id,i) == 1):
                if(semantic_alignment(row_mp, i, row_id) > 0.5):
                    return 1
                return 0
            i -= 1
        return 0


def row_label_prediction(row, predict_keys, metadata):

    #check if current row is a header or footer:
    row_phrases = []
    label = {}
    delta = 0.001
    for item in row:
        row_phrases.append(item[0])
    if(is_row_headers_or_footers(row_phrases, metadata) == 1):
        label['K'] = delta
        label['V'] = delta
        label['KV'] = delta
        label['M'] = 1
        add_metadata_row(row_phrases)
        return label 

    kvs = 0
    kks = 0 
    vvs = 0
    
    p_pre = row[0][0]
    for i in range(1,len(row)):
        p = row[i][0]
        if(p_pre in predict_keys and p in predict_keys):
            kks += 1
        elif(p_pre in predict_keys and p not in predict_keys):
            kvs += 1
        elif(p_pre not in predict_keys and p not in predict_keys):
            vvs += 1
        p_pre = p

    total = kvs + kks + vvs
    #print(kvs, kks, vvs)
    
    if(total == 0):
        label['K'] = delta
        label['V'] = delta
        label['KV'] = delta
        label['M'] = 2*delta
    else:
        label['K'] = kks/total+delta
        label['V'] = vvs/total+delta
        label['KV'] = kvs/total+delta
        label['M'] = 2*delta 
    return label


def print_row(row_mp):
    for row_id, lst in row_mp.items():
            print(row_id)
            p_print = []
            for (p,bb) in lst:
                p_print.append(p)
            print(p_print)

def print_row_labels(row_mp, row_labels):
    for row_id, lst in row_mp.items():
            print(row_id, row_labels[row_id])
            p_print = []
            for (p,bb) in lst:
                p_print.append(p)
            print(p_print)

def data_extraction_one_record(rid,rid_delta,blk,blk_type,row_mp,predict_labels): 
    #blk: bid -> list of row ids
    out = []
    record = {}
    record['id'] = rid

    # print('blk and blk type...')
    # print(blk, blk_type)

    for bid, lst in blk.items():
        # lst is a list of relative row ids in current data block 
        # need to modify the relative row id to global row id
        row_list = []
        for e in lst:
            row_list.append(e + rid_delta)
        
        #print(bid, blk_type[bid], row_list)

        object = {}
        if(blk_type[bid] == 'table'):
            object['type'] = 'table'
            key = [row_list[0]]
            vals = []
            for i in range(1,len(row_list)):
                vals.append(row_list[i])
            
            #print(key, vals)
            key, rows = table_extraction_top_down(row_mp, key, vals)
            #print(key, rows)
            content = []
            
            for row in rows:
                kvs = {}
                for i in range(len(key)):
                    k = key[i]
                    r = row[i]
                    kvs[k] = r
                content.append(kvs)
            #print(content)
            object['content'] = content 
        else:
            object['type'] = 'kv'
            kvs = []#kvs stores a list of tuples, where each tuple is (phrase, bb)
            for i in row_list:
                kvs += row_mp[i]
                kv_out = key_val_extraction(kvs, predict_labels)
            content = []
            
            for kv in kv_out:
                kvm = {}
                if(kv[1] == ''):
                    kvm[kv[0]] = 'missing'
                else:
                    kvm[kv[0]] = kv[1]
                content.append(kvm)
            object['content'] = content
        out.append(object)
    
    record['content'] = out

    return record

def data_extraction(records, blocks, row_mp, template):
    # blocks: record id -> (blk, blk_type) 
    # blk stores the relative id for current record, not global record id

    predict_labels = []
    out = []
    #print(blocks)
    #get predict labels 
    for node in template:
        predict_labels += node['fields']

    for rid in range(len(blocks)):
        record = records[rid]
        blk = blocks[rid][0]
        blk_type = blocks[rid][1]
        rid_delta = record[0]
        #print(rid, rid_delta)
        out_record = data_extraction_one_record(rid,rid_delta,blk,blk_type,row_mp,predict_labels)
        out.append(out_record)

        # if(rid >= 1):
        #     break

    return out


     

def write_string(result_path, content):
    with open(result_path, 'w') as file:
        file.write(content)

def kv_extraction(pdf_path, out_path, template_path, image_paths):
    metadata_path = key.get_metadata_path(pdf_path)
    metadata= []
    #print(metadata_path)
    if(not os.path.isfile(metadata_path)):
        out = get_metadata(image_paths)
        metadata = [phrase.strip() for phrase in out.split('|')]
        write_string(metadata_path, out)
    else:
        meta_string = read_string(metadata_path)
        metadata = [phrase.strip() for phrase in meta_string.split('|')]

    print('Metadata...')
    print(metadata)
    key_path = pdf_path.replace('data/raw','result').replace('.pdf','_TWIX_key.txt')
    extracted_path = key.get_extracted_path(pdf_path, 'plumber')
    
    if(not os.path.isfile(extracted_path)):
        return 
    if(not os.path.isfile(key_path)):
        return 
    bb_path = get_bb_path(extracted_path)
    
    #print(bb_path)
    keywords = read_file(key_path)#predicted keywords
    phrases = read_file(extracted_path)#list of phrases
    phrases_bb = read_json(bb_path)#phrases with bounding boxes

    #print(phrases_bb)
    print('Template-based data extraction starts...')

    mix_pattern_extract_pipeline(phrases_bb, keywords, phrases, out_path, template_path, metadata)

