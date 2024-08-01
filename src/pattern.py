import key,extract,json 

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

def pattern_detection(phrases, predict_labels, threshold = 0.9):
    phrases = record_extraction(phrases, predict_labels)
    #create key and value line vectors

    kv = []
    vv = []
    for i in range(len(phrases)):
        p = phrases[i]
        if(p in predict_labels):
            kv.append(i)
        else:
            vv.append(i)
    mismatch = 0
    for i in range(1,len(kv)):
        if(kv[i]-kv[i-1] > 1):
            mismatch += 1
    k_percentage = (len(kv)-mismatch)/len(kv)

    if(k_percentage > threshold):
        return 'table'
    else:
        return 'kv or mix'
    
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

def sort_val_based_on_bb_width(pv, predict_labels):
    new_pv = []
    for item in pv:
        p = item[0]
        bb = item[1]
        width = bb[2] - bb[0]
        new_pv.append((p,bb,width))
    sorted_list = sorted(new_pv, key=lambda x: x[2])
    return sorted_list

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


def table_extraction(phrases_bb, predict_labels, phrases):
    #get phrases for the first record 
    first_record = record_extraction(phrases, predict_labels)
    #print(first_record)
    #initialzie record_appearance
    record_appearance = {}
    for p in phrases:
        record_appearance[p] = 0
    #get the bounding box vector of phrases for the first record  
    record_appearance,pv = get_bb_per_record(record_appearance, phrases_bb, first_record)
    
    
    mp,footer = find_value_group(pv, predict_labels)
    for id, item in mp.items():
        print(id)
        for p in item:
            print(p[0])
    print('footer:')
    for p in footer:
        print(p[0])


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
    tested_id = 3 #starting from 1
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


        truths = format(read_file(truth_path))
        results = format(read_file(result_path))
        phrases = format(read_file(extracted_path))
        phrases_bb = format_dict(read_json(bb_path))

        table_extraction(phrases_bb, results, phrases)
        #print(pattern_detection(phrases, results))