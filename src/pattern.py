import key,extract,json,sys 
sys.path.append('/Users/yiminglin/Documents/Codebase/Pdf_reverse/')
from model import model 
model_name = 'gpt4o'

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

def key_val_extraction(phrases, predict_labels):
    kv = {}#relative location id -> (key,val)
    kk = {}#relative location id -> (key,key)
    vv = {}#relative location id -> (val,val)
    phrases = record_extraction(phrases, predict_labels)
    #phrases are the phrases one record
    ids = []
    for i in range(len(phrases)):
        p = phrases[i]
        if(p in predict_labels):
            if(i < len(phrases)-1 and phrases[i+1] not in predict_labels):#kv pair
                pn = phrases[i+1]
                kv[i] = (p,pn)
                ids.append(i)
                ids.append(i+1)
    #second pass: scan for kv and vv 
    i = 0
    while i < len(phrases):
        p = phrases[i]
        if(i in ids):#skip the kv pairs 
            i+=1
            continue
        # if(i < len(phrases)-1 and (i+1) in ids):
        #     i+=1
        #     continue
        if(p in predict_labels):
            if(i < len(phrases)-1 and phrases[i+1] in predict_labels):#kk pair
                pn = phrases[i+1]
                kk[i] = (p,pn)
                #i+=1
        else:
            if(i < len(phrases)-1 and phrases[i+1] not in predict_labels):#vv pair
                pn = phrases[i+1]
                vv[i] = (p,pn)
                #i+=1
        i+=1
        
    #process kk pair 
    for id, (p,pn) in kk.items():
        if(id in ids):#skip this pair since we don't want to modifty it
            continue
        if(id not in ids and id+1 in ids):#need to check
            kv[id] = (p,'missing')
            continue
        if(pair_oracle(p,pn) == 1):
            kv[id] = (p,pn)#insert into kv
            ids.append(id)
            ids.append(id+1)
        else:
            kv[id] = (p,'missing')
            ids.append(id)
    #process vv pair
    for id, (p,pn) in vv.items():
        if(id in ids):#skip this pair since we don't want to modifty it
            continue
        if(pair_oracle(p,pn) == 1):
            kv[id] = (p,pn)#insert into kv
            ids.append(id)
            ids.append(id+1)
    kv_out = []
    #search for consecutive vals 
    #add back consecutive values 
    # added = []
    # for id, (p,pn) in vv.items():
    #     if(id in added):
    #         continue
    #     if(id-2 in kv): 
    #         val = kv[id-1]
    #         while(True):
    #             if(id not in added):
    #                 val += p
    #                 added.append(id)
    #             if(id+1 not in added):
    #                 val += pn
    #                 added.append(id+1)
    #             if(id+1 not in vv or id == len(phrases)-1):#consecutive vals end
    #                 break
    #         kv[id-2] = val
    #produce final kv pairs 
    for id, (p,pn) in kv.items():
        kv_out.append((p,pn))
    return kv_out


def pair_oracle(left,right):
    instruction = 'The following two phrases are extracted from a table. ' 'Is ' + right + ' a possible value for the key word ' + left + '? Return only yes or no. '
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

def is_inclusive(b1,b2,delta = 1):
    #input: b1 and b2 are bounding box of two phrases 
    if (b1[0] <= b2[0] and b1[2]+delta >= b2[2]):
        return 1
    if (b2[0] <= b1[0] and b2[2]+delta >= b1[2]):
        return 1
    return 0

def is_aligned(b1,b2,delta = 0.5):
    if (b1[1] <= b2[1] and b1[3]+delta >= b2[3]):
        return 1
    if (b2[1] <= b1[1] and b2[3]+delta >= b1[3]):
        return 1
    return 0

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
                if(is_aligned(bi,bj) == 1):
                    is_match = 1
                    row_mp[id].append(t)
                    break
            if(is_match == 1):
                break
        if(is_match == 0):
            row_mp[row_id] = [t]
            row_id += 1

    #print(row_mp)

    new_row_mp = {}
    keys = sort_keys(key_mp, bbv)
    row_loc = {}# x['top']-> id
    #sort row based on keys
    print(len(row_mp))
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
                lst.append(('null',[0,0,0,0]))#denote missing value 
        row_loc[x_top] = id
        new_row_mp[id] = lst

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

def filter_key(bbv, phrases_bb, predict_labels):
    #output: a dict. cluster_id -> key
    vertical_dis = {}
    key_mp = {}
    for phrase, bb in phrases_bb.items():
        if(phrase in predict_labels):
            b = bb[0]
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
    mp = {}
    id = 0
    footer = []
    for item in pv:
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


def table_extraction(phrases_bb, predict_labels, phrases, path):
    #get phrases for the first record 
    first_record = record_extraction(phrases, predict_labels)
    #print(first_record)
    #initialzie record_appearance
    record_appearance = {}
    for p in phrases:
        record_appearance[p] = 0
    #get the bounding box vector of phrases for the first record  
    record_appearance,pv = get_bb_per_record(record_appearance, phrases_bb, first_record)
    
    
    vg,footer = find_value_group(pv, predict_labels)
    bbv = find_bb_value_group(vg)
    key_mp = filter_key(bbv, phrases_bb, predict_labels)
    headers = identify_headers(key_mp, predict_labels, footer)
    #print(headers)
    rows,keys = find_rows(vg, key_mp, bbv)
    # print(keys)
    # for row in rows:
    #     row_out = []
    #     for r in row:
    #         row_out.append(r[0])
    #     print(row_out)
    #write_table(keys, rows, path)
    print("headers:")
    for p in headers:
        print(p)
    print("footers")
    for p in footer:
        print(p[0])


def write_table(keys, rows, path):
    keys_out = ', '.join(keys)
    keys_out += '\n'
    
    with open(path, 'w') as file:
        file.write(keys_out)
        for row in rows:
            row_out = ''
            for r in row:
                row_out += r[0] + ','
            file.write(row_out[:-1]+'\n')
        #print(row_out[:-1])
            #print(row[0])
            # row_out = ', '.join(row[0][0])
            # file.write(row_out)

def format_dict(dict):
    d = {}
    for k,v in dict.items():
        d[k.lower()] = v
    return d

if __name__ == "__main__":
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
    tested_id = 2 #starting from 1
    k=1

    for path in tested_paths:
        id += 1
        if(id != tested_id):
            continue
        print(path)
        result_path = key.get_result_path(path)
        truth_path = key.get_truth_path(path,1)
        extracted_path = key.get_extracted_path(path)
        bb_path = get_bb_path(extracted_path)
        out_path = key.get_key_val_path(path)


        truths = format(read_file(truth_path))
        results = format(read_file(result_path))
        phrases = format(read_file(extracted_path))
        phrases_bb = format_dict(read_json(bb_path))

        #table_extraction(phrases_bb, results, phrases, out_path)
        #print(pattern_detection(phrases, results))
        kvs = key_val_extraction(phrases, results)
        for kv in kvs:
            print(kv)