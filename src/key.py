import json,os
import extract
import numpy as np
import scipy.stats
import sys
import time 
import networkx as nx
from nltk.tokenize import word_tokenize
import key 
import tiktoken
sys.path.append('/Users/yiminglin/Documents/Codebase/Pdf_reverse/')
from model import model 
model_name = 'gpt4o'
# available_encodings = tiktoken.list_encoding_names()
# print("Available encodings:", available_encodings)

tokenizer = tiktoken.get_encoding("cl100k_base")

def token_size(text):
    tokens = tokenizer.encode(text)
    num_tokens = len(tokens)
    return num_tokens

def get_relative_locations(path):
    #get raw phrases path
    path = get_extracted_path(path)
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


def get_extracted_path(path, method = 'plumber'):
    path = path.replace('raw','extracted')
    if('benchmark1' in path):
        path = path.replace('.pdf', '_' + method +  '.txt')
    else:
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

def load_candidate(pdf_path):
    path = pdf_path.replace('data/raw','result').replace('.pdf','_key.txt')
    cans = read_file(path)
    return cans

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

def perfect_align_clustering(phrases_vec,k=1):#k is the definition of partial perfect match
    mp = {}#phrase to cluster id
    remap = {}#cluster id to list of phrases
    id = 0
    phrases = []
    for phrase, vec in phrases_vec.items():
        if(len(vec) > 1):#phrase appearing only one time is trievally perfectly align with any other one-time phrase and discard them 
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


def result_gen_from_response(response, lp):
    s = len(lp)
    lst = []
    if('|' not in response and 'no' in response.lower()):
        for i in range(s):
            lst.append(0)
        return lst
    response = response.lower()
    lpn = []
    for p in lp:
        lpn.append(p.lower())
    #print(lpn)
    l = response.split('|')
    #print(l)
    for p in lpn:
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

def candidate_key_clusters_selection(clusters):
    #clusters: cid -> [list of phrases]
    instruction = 'The following list contains possibly keyword and values extracted from a table. Return to me all the keys without explanation, and seperate each keyword by |. If no key is found, return NO. Reminder: keyword will be not likely a number. ' 
    mp = {}
    cids = []
    input_size = 0
    output_size = 0
    for cid, l in clusters.items():
        
        if(len(l) <= 2):
            continue
        context = ", ".join(l)
        prompt = (instruction,context)
        response = model(model_name,prompt)

        input_size += token_size(instruction)
        input_size += token_size(context)
        output_size += token_size(response)

        lst = result_gen_from_response(response, l)
        p, w = mean_confidence_interval(lst)
        #important: if all 0, then confidence width is also 0, which makes other node hard dominate this one even it's the worst
        if(p == 0):
            continue
        # print(cid, p, w)
        # print(l)
        # print(response)
        # print(lst)
        mp[cid] = (p,w)
        cids.append(cid)

    #topology order to select maximal key set 
    out_degree = {}
    for i in range(len(cids)):
        ci = cids[i]
        for j in range(i+1, len(cids)):
            cj = cids[j]
            if(mp[ci][0] > mp[cj][0] and mp[ci][1] < mp[cj][1]):
                #ci dominates cj, add edge from cj to ci
                if(cj not in out_degree):
                    out_degree[cj] = 1
            elif(mp[ci][0] < mp[cj][0] and mp[ci][1] > mp[cj][1]):
                #cj dominates ci, add edge from ci to cj
                if(ci not in out_degree):
                    out_degree[ci] = 1
    candidate_key_clusters = []
    for cid in cids:
        if(cid not in out_degree):
            candidate_key_clusters.append(cid)
    #print(candidate_key_clusters)
    return candidate_key_clusters, input_size, output_size 

def mean_confidence_interval(data, confidence=0.95):
    a = 1.0 * np.array(data)
    n = len(a)
    m, se = np.mean(a), scipy.stats.sem(a)
    h = se * scipy.stats.t.ppf((1 + confidence) / 2., n-1)
    return m, h

def cluster_partial_match(c1,c2,phrases_vec,k):
    # print(c1)
    # print(c2)
    l1 = len(phrases_vec[c1[0]])
    l2 = len(phrases_vec[c2[0]])
    #print(l1,l2)
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
                #print(nc1[i],phrases_vec[nc1[i]])
                #print(nc2[j],phrases_vec[nc2[j]])
                #print('')
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

    #print(candidate_key_clusters)
    key_clusters += candidate_key_clusters
    #print(key_clusters)
    return key_clusters

def get_keys(cans, cluters, key_clusters):
    keys = []
    for key in key_clusters:
        keys += cluters[key]
    ks = set(keys).intersection(cans)
    return list(ks)

def get_result_path(raw_path, method = 'TWIX'):
    path = raw_path.replace('data/raw','out')
    path = path.replace('.pdf', '_' + method + '_key.txt')
    return path

def get_key_val_path(raw_path, approach):
    path = raw_path.replace('data/raw','out')
    path = path.replace('.pdf', '_' + approach + '_kv.json')
    return path

def get_baseline_result_path(raw_path,baseline_name):
    path = raw_path.replace('data/raw','result')
    path = path.replace('.pdf', '_' + baseline_name + '.txt')
    return path

def write_result(result_path, keys):
    with open(result_path, 'w') as file:
        # Iterate over each value in the list
        for value in keys:
            # Write each value to a separate line
            file.write(f"{value}\n")

def write_raw_response(result_path, content):
    with open(result_path, 'w') as file:
        file.write(content)

def get_truth_path(raw_path):
    path = raw_path.replace('raw','truths/')
    path = path.replace('.pdf','.json')
    return path



def key_prediction_pipeline(data_folder):
    paths = extract.print_all_document_paths(data_folder)
    for path in paths:
        key_prediction(path)

def key_prediction(pdf_path):
    result_path = get_result_path(pdf_path)
    extracted_path = get_extracted_path(pdf_path)
    #generate reading order vector
    relative_locations = get_relative_locations(pdf_path)
    reading_order_path = get_relative_location_path(extracted_path)
    #print(reading_order_path)
    #write_dict(reading_order_path, relative_locations)
    cans = load_candidate(pdf_path)

    #predict keys
    phrases = relative_locations
    print('perfect match starts...')
    mp, remap = perfect_align_clustering(phrases)
    #print(remap)
    print('cluster pruning starts...')
    candidate_key_clusters, input_size, output_size = candidate_key_clusters_selection(remap)
    print('re-clustering starts...')
    key_clusters = clustering_group(phrases, remap, candidate_key_clusters, k=1)
    keys = get_keys(cans, remap, key_clusters)
    #print(keys)
    #print('input and output token size:', input_size, output_size)
    #write result
    write_result(result_path,keys)

if __name__ == "__main__":
    root_path = extract.get_root_path()
    data_folder = root_path + '/data/extracted/complaints & use of force/'
    
    
    key_prediction_pipeline(data_folder)
    
        
        
        