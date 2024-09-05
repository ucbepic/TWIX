import key,extract,json,sys,csv,math
import numpy as np 
import key
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import min_weight_full_bipartite_matching
sys.path.append('/Users/yiminglin/Documents/Codebase/Pdf_reverse/')
from model import model 
model_name = 'gpt4o'
vision_model_name = 'gpt4vision'

def get_metadata(image_path = '/Users/yiminglin/Downloads/page_1.jpg'):
    instruction = 'Return the headers and footers in this page. Give me the raw output from the image directly, do not add any more text to clarify.' 
    context = ''
    prompt = (instruction,context)
    response = model(vision_model_name,prompt, image_path = image_path)
    #print(response)
    return response

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

def record_extraction(phrases,predict_labels):
    #only return the first record 
    first_key = 'null'
    ps = []
    for p in phrases:
        if(p == first_key):#check the first record
            break
        ps.append(p)
        if(p in predict_labels):
            if(first_key == 'null'):
                first_key = p
    #print(first_key)
    return ps 

def format(lst):
    l = []
    for v in lst:
        l.append(v.lower().strip())
    return l

def get_bb_path(extracted_file):
    file = extracted_file.replace('.txt','.json')
    return file 

def get_bb_phrase(phrase, c, phrases_bb):
    if(phrase not in phrases_bb):
        return (-1,-1,-1,-1)
    bbs = phrases_bb[phrase]
    if(c<len(bbs)):
        return bbs[c]
    return (-1,-1,-1,-1)

def get_bbdict_per_record(record_appearance, phrases_bb, phrases):
    #phrases: phrase -> a list of bounding box for all records 
    #record_appearance: phrase p->the number of appearances of p so far 
    #output: a dict. phrase -> a list of bounding box for the phrase in current record
    pv = {}
    non_dul_phrases = list(set(phrases))#remove duplicated phrases 
    for p in non_dul_phrases:
        c = phrases.count(p)
        if(p not in pv and p in phrases_bb):
            cur = record_appearance[p]
            lst = phrases_bb[p][cur: cur + c]
            pv[p] = lst
            record_appearance[p] = cur + c
    return record_appearance, pv

def outlier_detect(dis, threshold = 1):
    lst = []
    for id, d in dis.items():
        lst.append(d)
    
    mean = np.mean(lst)
    std = np.std(lst)
    
    outliers = []
    for value in lst:
        z_score = (value - mean) / std
        if np.abs(z_score) > threshold:
            outliers.append(value)
    if(len(outliers) == 0):
        return [], 0,0,[]

    cutoff = min(outliers)
    false_pairs = []
    for id, d in dis.items():
        if(d >= cutoff):
            false_pairs.append(id)
    #print(cutoff)
    sum = 0
    new_lst = []
    for val in lst:
        if(val >= cutoff):
            continue
        new_lst.append(val)
        sum += val
    new_mean = sum/(len(lst) - len(outliers))
    return false_pairs, cutoff, new_mean, new_lst

def is_outlier(lst, d):
    lst.append(d)
    threshold = 1  
    mean = np.mean(lst)
    std = np.std(lst)
    
    outliers = []
    for value in lst:
        z_score = (value - mean) / std
        if np.abs(z_score) > threshold:
            outliers.append(value)
    
    cutoff = min(outliers)
    #print(cutoff)
    if(d >= cutoff):#is an outlier
        return 1
    return 0

def bipartite_match(edges, num_nodes_A, num_nodes_B):
    #(left, right and weight)
    #left and right starting from 0
    # edges = [
    #     (0, 0, 3),
    #     (1, 0, 1),
    #     (0, 1, 10),
    #     (2, 0, 1),
    #     (2, 1, 2)
    # ]

    # num_nodes_A = 3
    # num_nodes_B = 2

    adjacency_matrix = np.full((num_nodes_A, num_nodes_B), np.inf)

    for u, v, w in edges:
        adjacency_matrix[u, v] = w

    csr_adjacency_matrix = csr_matrix(adjacency_matrix)

    row_ind, col_ind = min_weight_full_bipartite_matching(csr_adjacency_matrix)

    weight = 0
    matching = {}

    # Iterate over the indices returned by the matching function
    for row, col in zip(row_ind, col_ind):
        matching[row] = (col, adjacency_matrix[row,col])
        #weight += adjacency_matrix[row,col]
        #print(row, col)

    #print(weight)
    return matching

def key_val_bipartite_extraction(phrases, phrases_bb, predict_labels):
    #greedy seems better since biM is globally optimization and local noise would affect other results significantly 
    phrases = record_extraction(phrases, predict_labels)
    record_appearance = {}
    for p in phrases:
        record_appearance[p] = 0

    record_appearance,pv = get_bblist_per_record(record_appearance, phrases_bb, phrases)
    #pv: a list of tuple. Each tuple:  (phrase, bounding box) for current record 
    #construct graph 
    edges = []
    left_nodes = {}
    right_nodes = {}
    left_id = 0
    right_id = 0

    c = 0
    #construct nodes
    for t in pv:
        c+=1
        if(c>=20):
            break
        p = t[0]
        if(p in predict_labels):
            left_nodes[left_id] = t
            left_id += 1
        else:
            right_nodes[right_id] = t
            right_id += 1

    #construct edges 
    for i in range(left_id):
        for j in range(right_id):
            dis = min_distance(left_nodes[i][1], right_nodes[j][1])
            edges.append((i,j,dis))
            # if(left_nodes[i][0] == 'case number' and right_nodes[j][0] == '21-00017'):
            #     print(dis)
            #print(left_nodes[i][0],right_nodes[j][0], dis)

    print('------')
    #run bipartite_match
    matching = bipartite_match(edges, left_id, right_id)

    results = []
    #process matching
    for left, (right,weight) in matching.items():
        l = left_nodes[left][0]
        r = right_nodes[right][0]
        results.append((l,r))
        print(l,r,weight)
    return results


def greedy_key_val_extraction_pipeline(phrases, phrases_bb, predict_labels):
    phrases = record_extraction(phrases, predict_labels)
    record_appearance = {}
    for p in phrases:
        record_appearance[p] = 0

    record_appearance,pv = get_bblist_per_record(record_appearance, phrases_bb, phrases)
    greedy_key_val_extraction(pv, predict_labels)

def greedy_key_val_extraction(pv, predict_labels):
    
    #pv: a list of tuple. Each tuple:  (phrase, bounding box) for current record 
    #for each predicated key, find its nearest phrases as the value. 

    kvs = []
    kks = []
    found = {}
    ks = []
    vs = []

    for i in range(len(pv)):
        dis = 10000
        target = -1
        if(pv[i][0] not in predict_labels):
            vs.append(i)
            continue
            #print(pv[i][0])
        for j in range(i+1, len(pv)):#simple trick, value should appear later than key 
            if(i==j):
                continue
            d = min_distance(pv[i][1],pv[j][1]) 
            if(d < dis):
                target = j
                dis = d
        if(target != -1 and target not in found):#a new phrase is found
            if(pv[target][0] in predict_labels): #kk pair 
                kks.append((i,target))
                print(pv[i][0],pv[target][0],dis)
            else:#kv pair
                kvs.append((i,target))
                #print(pv[i][0],pv[target][0],dis)
                found[i] = 1
                found[target] = 1
        else:
            #for a key, the closest phrase has already matched with other
            ks.append(i)
            #print(pv[i][0])

    results = []

    #check kv pairs
    for kv in kvs:
        results.append((pv[kv[0]][0], pv[kv[1]][0]))

    return results

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

def key_val_extraction_pipeline(phrases, phrases_bb, predict_labels):
    #print(metadata)
    
    phrases = record_extraction(phrases, predict_labels)
    record_appearance = {}
    for p in phrases:
        record_appearance[p] = 0

    record_appearance,pv = get_bblist_per_record(record_appearance, phrases_bb, phrases)
    key_val_extraction(pv, predict_labels)

def key_val_extraction(pv, predict_labels):
    #metadata = get_metadata().lower()
    metadata = []
    kv = {}#relative location id -> (key,val)
    kk = {}#relative location id -> (key,key)
    vv = {}#relative location id -> (val,val)
    ids = []
    dis = {}
    for i in range(len(pv)):
        p = pv[i][0]
        # if('medical' in p):
        #     print(p)
        bbp = pv[i][1]
        if(p in predict_labels):
            if(i < len(pv)-1 and pv[i+1][0] not in predict_labels):#kv pair
                pn = pv[i+1][0]
                kv[i] = (p,pn)
                ids.append(i)
                ids.append(i+1)
                bbpn = pv[i+1][1]
                dis[i] = min_distance(bbp,bbpn)
                # print(p,pn,dis[i])
                # print(bbp)
                # print(bbpn)
    #print(dis)

    outliers, cutoff, new_mean, new_lst = outlier_detect(dis)
    
    #second pass: scan for kk and vv 
    
    for id in outliers:
        if(is_metadata(metadata, pv[id][0]) == 0):
            #print('outlier: ', pv[id][0])
            kv[id] = (pv[id][0],'')
            ids.append(id)

    single_v = []
    i = 0
    while i < len(pv):
        p = pv[i][0]
        if(i in ids):#skip the kv pairs 
            i+=1
            continue
        if(p in predict_labels):
            if(i < len(pv)-1 and pv[i+1][0] in predict_labels):#kk pair
                pn = pv[i+1][0]
                kk[i] = (p,pn)
            elif(i == len(pv)-1):
                kv[i] = (p,'')
        else:
            if(i < len(pv)-1 and pv[i+1][0] not in predict_labels):#vv pair
                pn = pv[i+1][0]
                vv[i] = (p,pn)
            else:
                #vk? 
                single_v.append(i)
        i+=1
        
    # print(kv)
    # print(kk)
    # print(vv)
    bad_kv = []
    #process kk pair 
    for id, (p,pn) in kk.items():
        if(id in ids):#skip this pair since we don't want to modifty it
            continue
        #print(p,pn)
        #if(pair_oracle(p,pn) == 1):
        if(len(new_lst) > 0 and is_outlier(new_lst, min_distance(pv[id][1],pv[id+1][1])) == False ):#valid distance or semantically same or  pair_oracle(p,pn) == 1
            kv[id] = (p,pn)#insert into kv
            ids.append(id)
            ids.append(id+1)
            #update pn: remove in kv pair starting with pn 
            for id, (pi,pni) in kv.items():
                if(pi == pn):
                    bad_kv.append(id)
                    break
        else:
                #print('not match')
            if(is_metadata(metadata,p) == 0):
                #print('kk:', p)
                kv[id] = (p,'')
                ids.append(id)
    
    #process vv pair
    for id, (p,pn) in vv.items():
        if(id in ids):#skip this pair since we don't want to modifty it
            continue
        if(pair_oracle(p,pn) == 1):
            kv[id] = (p,pn)#insert into kv
            #print('matched')
            ids.append(id)
            ids.append(id+1)

    #process single v
    for i in single_v:
        v = pv[i][0]
        
        if(key_oracle(v) == 1 and is_metadata(metadata, v) == 0):
            print('single v:', v)
            kv[i] = (v,'')

    kv_out = []
    # print(metadata)
    # print('-----')
    for id, (p,pn) in kv.items():
        if(id in bad_kv):
            continue
        if((is_metadata(metadata, p) == 1 and len(p) > 3) and (is_metadata(metadata, pn) == 1 and len(pn) > 3)):
            #print(p,pn)
            continue
        kv_out.append((p,pn))
    #print(kv_out)
    return kv_out

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


def pair_oracle(left,right):
    instruction = 'The following two phrases are extracted from a table. ' 'Is ' + right + ' a possible value for the key word ' + left + '? Return only yes or no. '
    context = ''
    prompt = (instruction,context)
    response = model(model_name,prompt)
    print(response)
    if('yes' in response.lower()):
        return 1
    return 0

def key_oracle(val):
    instruction = 'The following phrase is either a key word or value extracted from a table. ' 'If ' + val + ' a key word, return yes. If'  + val + ' is a value, return no. '
    context = ''
    prompt = (instruction,context)
    response = model(model_name,prompt)
    #print(response)
    if('yes' in response.lower()):
        return 1
    return 0

def pattern_detection(phrases, predict_labels, threshold_table = 0.9, threshold_kv = 0.5):
    phrases = record_extraction(phrases, predict_labels)
    #create key and value line vectors

    kv = []
    vv = []
    kv_match = 0
    for i in range(len(phrases)):
        p = phrases[i]
        if(p in predict_labels):
            kv.append(i)
            if(i < len(phrases)-1 and phrases[i+1] not in predict_labels):
                kv_match += 1
            # else:
            #     if(i < len(phrases)-1):
            #         print(print(p, '***', phrases[i+1]))
        else:
            vv.append(i)
        
    mismatch = 0
    for i in range(1,len(kv)):
        if(kv[i]-kv[i-1] > 1):
            mismatch += 1
    k_percentage = (len(kv)-mismatch)/len(kv)
    kv_percentage = kv_match/len(kv)
    #print(kv_percentage)
    if(k_percentage > threshold_table):
        return 'table'
    
    #if((1-k_percentage) )
    return 'mix'
    

def get_bblist_per_record(record_appearance, phrases_bb, phrases):
    #phrases: phrase -> a list of bounding box for all records 
    #record_appearance: phrase p->the number of appearances of p so far 
    #output: a list of tuple. Each tuple:  (phrase, bounding box) for current record 
    pv = []
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

            # print(p,c,appear[p],len(lst))
            # print(phrases_bb[p], cur, cur+c)
            bb = lst[appear[p]]
            # if('formal' in p):
            #     print(p,bb, appear[p])
            pv.append((p,bb))
    for p in phrases:
        if(p in phrases_bb):
            record_appearance[p] = record[p]
            
    return record_appearance, pv

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
    # if (b1[1] <= b2[1] and b1[3]+delta >= b2[3]):
    #     return 1
    # if (b2[1] <= b1[1] and b2[3]+delta >= b1[3]):
    #     return 1
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

def hash_tuple(tuple):
    p = tuple[0]
    bb = tuple[1]
    return (p,bb[0],bb[1],bb[2],bb[3])

def find_rows(vg, key_mp, bbv):
    #key_mp: cluster_id -> key
    #input: a cluster dict. Cluster id -> a list of tuples. Each tuple:  (phrase, bounding box) 
    #output: row_id -> a list of tuples. Each tuple:  (phrase, bounding box) 
    row_id = 0
    row_mp = {}
    pb = []
    re_map = {}#tuple -> key cluster_id
    for id, tuples in vg.items():
        if(id not in key_mp):
            continue
        key = key_mp[id]
        #print(key, id)
        for t in tuples:
            #print(t)
            pb.append(t)
            re_map[hash_tuple(t)] = key
    for t in pb:
        pi = t[0]
        bi = t[1]
        is_match = 0
        for id, tuples in row_mp.items():#scan cluster
            for tt in tuples:
                pj = tt[0]
                bj = tt[1]
                #print(bi,bj, is_aligned(bi,bj))
                if(is_aligned(bi,bj) == 1):
                    #print(bi,bj)
                    is_match = 1
                    row_mp[id].append(t)
                    break
            if(is_match == 1):
                break
        if(is_match == 0):
            row_mp[row_id] = [t]
            row_id += 1

    # for id, lst in row_mp.items():
    #     print(id)
    #     for (p,bb,w) in lst:
    #         print(p)

    new_row_mp = {}
    keys = sort_keys(key_mp, bbv)
    row_loc = {}# x['top']-> id
    #sort row based on keys
    #print(len(row_mp))
    for id, tuples in row_mp.items():
        lst = []
        quick_mp = {}
        for t in tuples:
            key = re_map[hash_tuple(t)]
            quick_mp[key] = t
        x_top = 0
        for key in keys:
            if(key in quick_mp):
                tuple = quick_mp[key]
                lst.append(tuple)
                x_top = tuple[1][1]
            else:
                lst.append(('',[0,0,0,0]))#denote missing value 
        row_loc[x_top] = id
        new_row_mp[id] = lst

    # for id, lst in new_row_mp.items():
    #     print(id)
    #     #print(lst)
    #     for item in lst:
    #         print(item[0])

    #sort row based on bound box 
    sorted_rows = []
    sorted_row_loc = dict(sorted(row_loc.items()))
    #print(sorted_row_loc)
    for x_top, id in sorted_row_loc.items():
        sorted_rows.append(new_row_mp[id])

    return sorted_rows, keys




def sort_val_based_on_bb_width(pv, predict_labels):
    new_pv = []
    for item in pv:
        p = item[0]
        bb = item[1]
        width = bb[2] - bb[0]
        new_pv.append((p,bb,width))
    sorted_list = sorted(new_pv, key=lambda x: x[2])
    return sorted_list

def find_bb_value_group(vg):
    #input vg (val_group): cluster_id -> a list of tuples. Each tuple: (phrase, bb)
    #output: cluster_id -> bb of value group
    bbv = {}
    max = 10000
    min = 0
    for id, tuples in vg.items():
        b0 = max#x0
        b1 = max#top
        b2 = min#x1
        b3 = min#bottem
        for tuple in tuples:
            b = tuple[1]
            if(b[0] <= b0):
                b0 = b[0]
            if(b[2] >= b2):
                b2 = b[2]
            if(b[1] <= b1):
                b1 = b[1]
            if(b[3] >= b3):
                b3 = b[3]
        bbv[id] = (b0,b1,b2,b3)
    return bbv

def identify_headers(key_mp, predict_labels, footers):
    headers = []
    keys = []
    for id, key in key_mp.items():
        keys.append(key)
    for key in predict_labels:
        if(key not in keys and key not in footers):
            headers.append(key)
    return headers

def filter_key(bbv, pv, predict_labels):
    #output: a dict. cluster_id -> key
    vertical_dis = {}
    key_mp = {}
    for (phrase, b) in pv: 
        if(phrase in predict_labels):
            #print(phrase)
            #find the cloest key per value group
            for id, bb in bbv.items():
                if(is_inclusive(b,bb) == 1):
                    vdis = bb[1] - b[3]
                    if(id not in key_mp):
                        key_mp[id] = phrase
                        vertical_dis[id] = vdis
                    else:
                        if(vdis <= vertical_dis[id]):#update to the closest key 
                            key_mp[id] = phrase
                            vertical_dis[id] = vdis
    return key_mp
                    
def sort_keys(key_mp, bbv):
    #key_mp: cluster_id -> key
    #bbv: cluster_id -> bounding box of value group
    keys = []
    keys_bb = []
    for id, key in key_mp.items():
        bb = bbv[id]
        keys_bb.append((key,bb[0]))
    sorted_keys = sorted(keys_bb, key=lambda x: x[1])
    for key in sorted_keys:
        keys.append(key[0])
    return keys 

def find_value_group(pv, predict_labels):
    pv = sort_val_based_on_bb_width(pv, predict_labels)

    #input: a list of tuples. Each tuple:  (phrase, bounding box) 
    #output: a cluster dict. Cluster id -> a list of tuples
    # a tuple: (phrase, bounding box, width of bounding box)
    mp = {}
    id = 0
    footer = []
    for item in pv:
        #print(item)
        pi = item[0]
        if(pi in predict_labels):#skip keys, consider values 
            continue
        bbi = item[1]
        #print('***', pi,bbi)
        is_match = 0 
        matched_id = -1
        for i in range(id):#scan cluster 
            lst = mp[i]
            for pb in lst:
                pj = pb[0]
                bbj = pb[1]
                if(is_inclusive(bbi,bbj) == 1):
                    #add to current cluster 
                    # print(pi,pj)
                    # print(bbi,bbj)
                    #mp[i].append(item)
                    matched_id = i
                    is_match += 1
                    break
            if(is_match > 1):
                break
        if(is_match == 0):#there is no cluster matching with current item, create a new cluster
            mp[id] = [item]
            id += 1
        if(is_match == 1):
            mp[matched_id].append(item)
        if(is_match > 1):
            footer.append(item)
    return mp,footer

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
        t_val = 'null'
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
    return keys, rows


    

    
    


def table_extraction(predict_labels, pv, path):
    # for item in pv:
    #     print(item)
    vg,footer = find_value_group(pv, predict_labels)
    # for id, lst in vg.items():
    #     print(id)
    #     for item in lst:
    #         print(item[0])
        
    bbv = find_bb_value_group(vg)
    key_mp = filter_key(bbv, pv, predict_labels)
    headers = identify_headers(key_mp, predict_labels, footer)
    print(headers)
    # for id, vals in key_mp.items():
    #     print(id)
    #     print(vals)
    
    rows,keys = find_rows(vg, key_mp, bbv)
    #print(rows, keys)
    print_table(keys, rows)

def table_extraction_pipeline(phrases_bb, predict_labels, phrases, path):
    #get phrases for the first record 
    first_record = record_extraction(phrases, predict_labels)
    record_appearance = {}
    for p in phrases:
        record_appearance[p] = 0
    #get the bounding box vector of phrases for the first record  
    record_appearance,pv = get_bb_per_record(record_appearance, phrases_bb, first_record)
    table_extraction(predict_labels, pv, path)

def print_table(keys, rows):
    keys_out = ', '.join(keys)
    keys_out += '\n'
    
    print(keys_out)
    for row in rows:
        row_out = ''
        for r in row:
            row_out += r[0] + ','
        print(row_out[:-1])

def write_table(keys, rows, path):
    keys_out = ', '.join(keys)
    keys_out += '\n'
    
    with open(path, 'w') as file:
        file.write(keys_out)
        #print(keys_out)
        for row in rows:
            row_out = ''
            for r in row:
                row_out += r[0] + ','
            file.write(row_out[:-1]+'\n')
            #print(row_out[:-1])

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
    while(id1 < len(row1) and id2 < len(row2)):
        if(is_overlap_vertically(row2[id2][1], row1[id1][1]) == 1 and is_overlap_vertically(row2[id2][1], row1[id1-1][1]) == 1):
            print('overlapping two')
            return 0
        #print(row1[id1][1][2], row2[id2][1][2])
        if(row1[id1][1][2] < row2[id2][1][2]):
            id1 += 1
        else:
            id2 += 1

    #check if there exist a phrase in row2 that does not overlapps with ant of val in row1
    
    for (p2,bb2) in row2:
        valid = 0
        for (p1,bb1) in row1:
            if(is_overlap_vertically(bb2,bb1) == 1):
                valid = 1
                break
        if(valid == 0):
            print(p2)
            return 0
    return 1

    

def row_pattern(lst, predict_labels, new_lst, esp = 0.5):
    kvs = 0
    kks = 0 
    vvs = 0
    p_pre = lst[0][0]
    bb_pre = lst[0][1]
    for i in range(1,len(lst)):
        p = lst[i][0]
        bb = lst[i][1]
        if(p_pre in predict_labels and p in predict_labels):
            kks += 1
        elif(p_pre in predict_labels and p not in predict_labels):
            #if(is_outlier(new_lst,min_distance(bb,bb_pre)) == 0):
                kvs += 1
                #print(p_pre,p)
            # else:
            #     vvs += 1
            #print(p_pre,p)
        elif(p_pre not in predict_labels and p not in predict_labels):
            vvs += 1
        p_pre = p
        
    size = kks + kvs + vvs
    #print(kks, kvs, vvs)
    if(size == 0):
        return 'undefined'
    
    if(kks / size > esp):
        return 'key'
    
    if(kvs / size > esp):
        return 'kv'
    
    if(vvs / size > esp):
        return 'val'
    
    return 'undefined'

    # if(max(kks,kvs,vvs) == kks):
    #     return 'key'
    # if(max(kks,kvs,vvs) == kvs):
    #     return 'kv'
    # if(max(kks,kvs,vvs) == vvs):
    #     return 'val'
    
def check_vadility(row_mp, rls, id): 
    if(rls[id] == 'undefined'):
        return 'undefined'
    
    if(rls[id] == 'key'):
        #for a 'key' row, if there is no aligned val row under it, make it to be undefined
        valid = 0
        nid = id
        while(True):
            nid += 1
            if(nid >= len(row_mp)):
                break
            if(rls[nid] == 'kv' or rls[nid] == 'key'):#mark the end of current table block
                #print('kv or key')
                break
            if(rls[nid] == 'val' and row_aligned(row_mp[id], row_mp[nid])==1):
                valid = 1
                break
        if(valid == 0):
            return 'undefined'
        else:
            return 'key'
        
    if(rls[id] == 'val'):
        #for a 'val' row, if there is no aligned key row above it, make it to be undefined
        valid = 0
        nid = id
        while(True):
            nid -= 1
            if(nid <= 0):
                break
            if(rls[nid] == 'key' and row_aligned(row_mp[nid],row_mp[id]) == 1):
                valid = 1
                break
            if(rls[nid] == 'key' and row_aligned(row_mp[nid],row_mp[id]) == 0):
                break
            if(rls[nid] == 'kv'):
                break
        if(valid == 0):
            return 'undefined'
        else:
            return 'val'
    return rls[id]
        
def infer_undefined(row_mp, rls):
    #guess the label of undefined rows based on rules 
    a=0
 
def pattern_detect_by_row(pv, predict_labels):
    #refine kv pair by using distance constraint
    kv = {}
    ids = []
    dis = {}
    for i in range(len(pv)):
        p = pv[i][0]
        bbp = pv[i][1]
        if(p in predict_labels):
            if(i < len(pv)-1 and pv[i+1][0] not in predict_labels):#kv pair
                pn = pv[i+1][0]
                kv[i] = (p,pn)
                ids.append(i)
                ids.append(i+1)
                bbpn = pv[i+1][1]
                dis[i] = min_distance(bbp,bbpn)

    outliers, cutoff, new_mean, new_lst = outlier_detect(dis)
    # for i in outliers:
    #     print(kv[i])

    
    #input: a list of tuple. Each tuple:  (phrase, bounding box) for current record
    p_pre = pv[0][0]
    bb_pre = pv[0][1]
    row_id = 0
    row_mp = {} #row_id -> a list of (phrase, bb) in the current row
    row_mp[row_id] = []
    row_mp[row_id].append((p_pre, bb_pre))
    for i in range(1, len(pv)):
        p = pv[i][0]
        bb = pv[i][1]
        if(is_same_row(bb_pre,bb) == 0):
            row_id += 1
            row_mp[row_id] = []
        row_mp[row_id].append((p, bb))
        p_pre = p
        bb_pre = bb

    rls = {}
    for row_id, lst in row_mp.items():
        row = []
        for l in lst:
            row.append(l[0])
        row_label = row_pattern(lst, predict_labels, new_lst)
        rls[row_id] = row_label
        

    #check the validity of the labels by using rules 
    for row_id, lst in row_mp.items():
        print(row_id)
        p_print = []
        for (p,bb) in lst:
            p_print.append(p)
        print(p_print)
        new_label = check_vadility(row_mp, rls, row_id)
        print(rls[row_id], new_label)
        rls[row_id] = new_label
        

    # for id, label in rls.items():
    #     print(id, label)
    blk, blk_id = block_decider(rls)
    
    return blk, blk_id, row_mp
    
    
    
def block_decider(rls):
    blk = {}#store the community of all rows belonging to the same block
    blk_id = {}#store the 
    bid = 0
    status = ''
    for id, label in rls.items():
        if(label == 'key'):
            bid += 1
            blk[bid] = []
            blk[bid].append(id)
            blk_id[bid] = 'table'
            status = 'key'
        elif(label == 'val' and status == 'key'):
            blk[bid].append(id)
        elif(label == 'kv' and status != 'kv'):#start a new block for kv
            bid += 1
            blk[bid] = []
            blk[bid].append(id)
            status = 'kv'
            blk_id[bid] = 'kv'
        elif(label == 'kv' and status == 'kv'):
            blk[bid].append(id)
    return blk, blk_id


def mix_pattern_extract_pipeline(phrases_bb, predict_labels, phrases, path):
    #get the first record
    phrases = record_extraction(phrases, predict_labels)
    #print(phrases)
    record_appearance = {}
    for p in phrases:
        record_appearance[p] = 0

    record_appearance,pv = get_bblist_per_record(record_appearance, phrases_bb, phrases)
    
    mix_pattern_extract(predict_labels, pv,path)

def mix_pattern_extract(predict_labels, pv, path):
    
    #pv: a list of tuple. Each tuple:  (phrase, bounding box) for current record 
    
    # for item in pv:
    #     print(item[0])

    blk, blk_id, row_mp = pattern_detect_by_row(pv, predict_labels)

    out = ''

    for id, lst in blk.items():
        out += blk_id[id] + '\n'
        if(blk_id[id] == 'table'):
            a=0
            #print(blk_id[id],lst)#lst is the list of row ids belonging to the same community
            key = [lst[0]]
            vals = []
            for id in range(1,len(lst)):
                vals.append(lst[id])
            key, rows = table_extraction_top_down(row_mp, key, vals)
            #print(key)
            out += ", ".join(key) + '\n'
            for row in rows:
                #print(row)
                out += ", ".join(row) + '\n'
        else:
            
            #print(blk_id[id],lst)
            kvs = []#kvs stores a list of tuples, where each tuple is (phrase, bb)
            # for id in lst:
            #     kvs += row_mp[id]
            # kv_out = key_val_extraction(kvs, predict_labels)
            # for kv in kv_out:
            #     out += kv[0] + ',' + kv[1] + '\n'
            #print(kv_out)
        out += '\n'
    #print(out)
    #write_string(path, out)
        

def write_string(result_path, content):
    with open(result_path, 'w') as file:
        file.write(content)

if __name__ == "__main__":
    #print(get_metadata())
    root_path = extract.get_root_path()
    #print(root_path)
    tested_paths = []
    tested_paths.append(root_path + '/data/raw/complaints & use of force/Champaign IL Police Complaints/Investigations_Redacted.pdf')
    tested_paths.append(root_path + '/data/raw/complaints & use of force/UIUC PD Use of Force/22-274.releasable.pdf')
    tested_paths.append(root_path + '/data/raw/certification/CT/DecertifiedOfficersRev_9622 Emilie Munson.pdf')
    tested_paths.append(root_path + '/data/raw/certification/IA/Active_Employment.pdf')
    tested_paths.append(root_path + '/data/raw/certification/MT/RptEmpRstrDetail Active.pdf')
    tested_paths.append(root_path + '/data/raw/certification/VT/Invisible Institue Report.pdf')

    id = 0
    tested_id = 6 #starting from 1
    k=1

    #pair_oracle('name','joe')

    for path in tested_paths:
        id += 1
        if(id != tested_id):
            continue
        print(path)
        result_path = key.get_result_path(path)
        truth_path = key.get_truth_path(path,1)
        extracted_path = key.get_extracted_path(path)
        bb_path = get_bb_path(extracted_path)
        out_path = key.get_key_val_path(path, '')


        truths = format(read_file(truth_path))
        results = read_file(result_path)
        phrases = read_file(extracted_path)
        phrases_bb = read_json(bb_path)

        #print(out_path)
        mix_pattern_extract_pipeline(phrases_bb, results, phrases, out_path)


        #table_extraction_pipeline(phrases_bb, results, phrases, out_path)
        #kvs = key_val_extraction(phrases, phrases_bb, results)
        #write_result(kvs,out_path)
        # for kv in kvs:
        #     print(kv)