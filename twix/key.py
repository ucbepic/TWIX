import json, os
from . import extract, cost 
import numpy as np
import scipy.stats
import sys
import tiktoken
root_path = extract.get_root_path()
sys.path.append(root_path)
from twix.model import model 
model_name = 'gpt-4o'
vision_model_name = 'gpt4vision'
total_cost = 0

tokenizer = tiktoken.get_encoding("cl100k_base")


def get_fields_by_LLM(image_paths):
    #prompt = 'The given two images have common headers and footers in the top and bottem part of the image. Return only the raw headers and footers. Do not return other phrases. Do not add any explanations. '
    prompt = 'Extract the set of keywords from the given two images. A keyword can be in the table header or in every key value pairs. Return the raw distinct keyword, seperated by |. Do not add explanations. Do not include headers or footers. Do not include other phrases like table values. ' 
    
    response = model(vision_model_name,prompt,image_paths)
    fields = [phrase.strip() for phrase in response.split('|')]

    global total_cost
    total_cost += cost.cost(model_name, 0, cost.count_tokens(response, model_name), image_num=2)  

    return fields 

def token_size(text):
    tokens = tokenizer.encode(text)
    num_tokens = len(tokens)
    return num_tokens

def get_relative_locations(path):
    line_number = 0
    phrases = {}
    with open(path, 'r') as file:
        # Iterate over each line in the file
        for line in file:
            phrase = line.strip()
            if(phrase not in phrases):
                phrases[phrase] = [line_number]
            else:
                phrases[phrase].append(line_number)
            line_number += 1
    return phrases
            
def write_dict(path, d):
    with open(path, 'w') as json_file:
        json.dump(d, json_file)

def read_dict(file):
    #print(file)
    with open(file, 'r') as file:
        data = json.load(file)
    return data 

def get_metadata_path(result_folder):
    return result_folder + 'metadata.txt' 

def get_metadata_row_path(result_folder):
    return result_folder + 'metadata_rows.txt' 

def get_extracted_path(path, method = 'plumber'):
    path = path.replace('raw','extracted')
    if('benchmark1' in path):
        path = path.replace('.pdf', '_' + method +  '.txt')
    else:
        #path = path.replace('.pdf', '_' + method +  '.txt')
        path = path.replace('.pdf', '.txt')
    return path

def read_file(file):
    data = []
    with open(file, 'r') as file:
        # Iterate over each line in the file
        for line in file:
            # Print the line (you can replace this with other processing logic)
            data.append(line.strip())
    return data

def get_extracted_image_path(path,page_id):
    path = path.replace('raw','extracted')
    path = path.replace('.pdf','_' + str(page_id) + '.jpg')
    return path

def get_relative_location_path(extracted_path, method = 'plumber'):
    path = extracted_path[:-4] + '_' + method + '_relative_location.csv'
    return path

def perfect_match(v1,v2,k):
    if(len(v1)!=len(v2)):
        return 0
    delta = abs(v1[0] - v2[0])
    for i in range(len(v1)):
        #print(abs(abs(v1[i]-v2[i])-delta))
        if(abs(abs(v1[i]-v2[i])-delta) > k):
            #print(delta, v1[i],v2[i])
            return 0
    return 1


def is_subsequence(seq1, seq2, k):#len(seq1) < len(seq2)
    i = 0
    j = 0 
    matched_count = 0
    while(True):
        if(abs(seq1[i] - seq2[j]) <= k):
            matched_count += 1
            i += 1
            j += 1
        else:
            j += 1
        if(i == len(seq1) or j == len(seq2)):
            break
    if(matched_count < len(seq1)):
        return 0
    return 1


def partial_perfect_match(v1,v2,k):#len(v1) < len(v2)
    delta = abs(v1[0] - v2[0])
    new_v1 = []
    if(v1[0] < v2[0]):
        for v in v1:
            new_v1.append(v + delta)
    else:
        for v in v1:
            new_v1.append(v - delta)
    return is_subsequence(new_v1,v2,k)

def perfect_align_clustering(phrases_vec,k=1, least_record_number = 3):#k is the definition of partial perfect match
    mp = {}#phrase to cluster id
    remap = {}#cluster id to list of phrases
    id = 0
    phrases = []
    for phrase, vec in phrases_vec.items():
        if(len(vec) > least_record_number):#phrase appearing only one time is trievally perfectly align with any other one-time phrase and discard them 
            phrases.append(phrase)

    for i in range(len(phrases)):
        pi = phrases[i]
        vi = phrases_vec[pi]
        if(pi not in mp):
            mp[pi] = id
            remap[id] = [pi]
            id += 1
        else:
            continue
        for j in range(i+1, len(phrases)):
            pj = phrases[j]
            vj = phrases_vec[pj]

            #optimization: pj in mp denotes that pj must be at least perfectly match with one phrase before pi, but pi is not in mp
            #so pi and pj must be not perfectly aligned, and thus skip comparison 
            if(pj in mp):
                continue

            if(perfect_match(vi,vj,k) == 1):
                mp[pj] = id-1
                remap[id-1].append(pj)
    
    return mp, remap

def clean_phrases(response, lp):
    l = response.split('|')
    lp_lower = []
    for p in lp:
        lp_lower.append(p.lower())
    out = []
    for p in l:
        if(p.strip().lower() in lp_lower):
            out.append(p.strip())
    return out 

def result_gen_from_response(response, lp):
    #lp is the original list 
    s = len(lp)
    lst = []
    if('|' not in response and 'no' in response.lower()):
        for i in range(s):
            lst.append(0)
        return lst
    response = response.lower()
    lp_lower = []
    for p in lp:
        lp_lower.append(p.lower())
    #print(lpn)
    l = response.split('|')
    #print(l)
    for p in lp_lower:
        if(p.isdigit()):#rule: a key cannot be a number 
            lst.append(0)
            continue
        is_match = 0
        for pl in l:
            if(pl.strip() == p):
                is_match = 1
                break
        if(is_match == 0):
            lst.append(0)
        else:
            lst.append(1)
    #print(lst)
    return lst

def phrase_filter_LLMs(l):#l is the list of phrases in the cluster 
    instruction = 'The following list contains possibly keyword and values. Return to me all the keywords without explanation, and seperate each keyword by |. If no key is found, return NO. Reminder: keyword will be not likely a number. '

    context = ", ".join(l)
    prompt = (instruction,context)
    response = model(model_name,prompt)

    global total_cost
    total_cost += cost.cost(model_name, cost.count_tokens(prompt[0] + prompt[1], model_name), cost.count_tokens(response, model_name)) 

    return response 


def candidate_key_clusters_selection(clusters, LLM_fields):
    #clusters: cid -> [list of phrases]
    
    cids = []
    out = []
    cids = []
    for cid, l in clusters.items():
        
        if(len(l) <= 2):
            continue
        response = phrase_filter_LLMs(l)
        fields = clean_phrases(response, l)
        lst = result_gen_from_response(response, l)
        p, w = mean_confidence_interval(lst)

        match = 0
        for f in fields:
            if(f in LLM_fields):
                match = 1
                break
        
        if(match == 1 or (p > 0.5 and w < 0.5)):
            out += fields
            cids.append(cid)

    #     lst = result_gen_from_response(response, l)
    #     p, w = mean_confidence_interval(lst)

    #     print(lst)
    #     print(p,w)
    #     #important: if all 0, then confidence width is also 0, which makes other node hard dominate this one even it's the worst
    #     if(p == 0):
    #         continue
    #     # print(cid, p, w)
    #     # print(l)
    #     # print(response)
    #     # print(lst)
    #     mp[cid] = (p,w)
    #     cids.append(cid)

    # #topology order to select maximal key set 
    # out_degree = {}
    # for i in range(len(cids)):
    #     ci = cids[i]
    #     for j in range(i+1, len(cids)):
    #         cj = cids[j]
    #         if(mp[ci][0] > mp[cj][0] and mp[ci][1] < mp[cj][1]):
    #             #ci dominates cj, add edge from cj to ci
    #             if(cj not in out_degree):
    #                 out_degree[cj] = 1
    #         elif(mp[ci][0] < mp[cj][0] and mp[ci][1] > mp[cj][1]):
    #             #cj dominates ci, add edge from ci to cj
    #             if(ci not in out_degree):
    #                 out_degree[ci] = 1
    # candidate_key_clusters = []
    # for cid in cids:
    #     if(cid not in out_degree):
    #         candidate_key_clusters.append(cid)
    # #print(candidate_key_clusters)
    return out,cids
    #return candidate_key_clusters, input_size, output_size 

def mean_confidence_interval(data, confidence=0.95):
    a = 1.0 * np.array(data)
    n = len(a)
    m, se = np.mean(a), scipy.stats.sem(a)
    h = se * scipy.stats.t.ppf((1 + confidence) / 2., n-1)
    return m, h

def cluster_partial_match(c1,c2,phrases_vec,k):
    l1 = len(phrases_vec[c1[0]])
    l2 = len(phrases_vec[c2[0]])
    nc1 = []
    nc2 = []
    if(l1 < l2):
        nc1 = c1
        nc2 = c2
    else:
        nc1 = c2
        nc2 = c1
    for i in range(len(nc1)):
        for j in range(len(nc2)):
            if(partial_perfect_match(phrases_vec[nc1[i]],phrases_vec[nc2[j]],k) == 1):
                return 1
    return 0
        

def clustering_group(phrases_vec, clusters, candidate_key_clusters, k=1):
    key_clusters = []
    for cid, vals in clusters.items():
        l1 = len(phrases_vec[vals[0]])
        
        if(cid in candidate_key_clusters):
            continue
        for k_cid in candidate_key_clusters:
            l2 = len(phrases_vec[clusters[k_cid][0]])
            if(l1 < l2):
                continue
            if(cluster_partial_match(clusters[cid], clusters[k_cid], phrases_vec, k) == 1):
                key_clusters.append(cid)
                break

    return key_clusters

def get_keys(cluters, key_clusters):
    keys = []
    for key in key_clusters:
        l = cluters[key]    
        keys += l
    return keys

def get_key_path(result_folder, method = 'twix'):
    return result_folder + method + '_key.txt'

def get_key_val_path(raw_path, approach):
    path = raw_path.replace('data/raw','result')
    path = path.replace('.pdf', '_' + approach + '_kv.json')
    return path

def get_template_path(result_folder):
    return result_folder +  'template.json'

def get_image_path(target_folder):
    paths = []
    path = target_folder + '_image/0.jpg'
    paths.append(path)
    path = target_folder + '_image/1.jpg'
    paths.append(path)
    return paths

def get_bb_path(result_folder):
    return result_folder + 'merged_raw_phrases_bounding_box_page_number.txt'

def write_result(result_path, keys):
    with open(result_path, 'w') as file:
        # Iterate over each value in the list
        for value in keys:
            # Write each value to a separate line
            file.write(f"{value}\n")

def get_merged_extracted_path(result_folder):
    return result_folder + 'merged_phrases.txt'

def get_extracted_result_path(result_folder, data_file):#file path is the path of each individual file 
    # Extract the directory and file name without the extension
    file_name = extract.get_file_name(data_file)

    # Construct the new file path with the desired suffix and extension
    new_file_path = os.path.join(result_folder, f"{file_name}_extracted.json")
    return new_file_path

def predict_field(data_files, result_folder, LLM_model_name = 'gpt-4o'):
    global model_name
    if len(LLM_model_name) > 0:
        model_name = LLM_model_name 
        
    if(len(result_folder) == 0):
        result_folder = extract.get_result_folder_path(data_files)
        
    extracted_path = get_merged_extracted_path(result_folder)

    #print(extracted_path)

    #get image path
    image_paths = get_image_path(result_folder)

    raw_phrases = read_file(extracted_path)
    raw_phrases = set(raw_phrases)
    #print(extracted_path)

    # #generate reading order vector
    relative_locations = get_relative_locations(extracted_path)
    #predict keys

    print('Field prediction starts...')
    phrases = relative_locations

    LLM_fields = get_fields_by_LLM(image_paths)
    LLM_fields = set(LLM_fields).intersection(raw_phrases)

    print('perfect match starts...')
    mp, remap = perfect_align_clustering(phrases)
    #print(remap)

    print('cluster pruning starts...')
    fields, cluster_ids = candidate_key_clusters_selection(remap,LLM_fields)

    print('re-clustering starts...')
    added_clusters = clustering_group(phrases, remap, cluster_ids, k=1)
    additional_fields = get_keys(remap, added_clusters)
    additional_fields = list(LLM_fields.intersection(set(additional_fields)))
    fields += additional_fields
    
    #write result
    result_path = get_key_path(result_folder)
    #print(result_path)
    write_result(result_path,fields)

    return fields, total_cost


    
        
        
        