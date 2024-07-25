import json
import extract
import math

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


def get_extracted_path(path):
    path = path.replace('raw','extracted')
    path = path.replace('.pdf','.txt')
    return path

def get_relative_location_path(extracted_path):
    path = extracted_path[:-4] + '_relative_location.csv'
    return path

def perfect_match(v1,v2):
    if(len(v1)!=len(v2)):
        return 0
    delta = abs(v1[0] - v2[0])
    for i in range(len(v1)):
        if(abs(v1[i]-v2[i]) != delta):
            return 0
    return 1
    
def is_subsequence(seq1, seq2):#len(seq1) < len(seq2)
    iter_seq2 = iter(seq2)
    return all(item in iter_seq2 for item in seq1)

def partial_perfect_match(v1,v2):#len(v1) < len(v2)
    delta = abs(v1[0] - v2[0])
    new_v1 = []
    if(v1[0] < v2[0]):
        for v in v1:
            new_v1.append(v + delta)
    else:
        for v in v1:
            new_v1.append(v - delta)
    if(is_subsequence(new_v1,v2)):
        return 1
    return 0

def perfect_align_clustering(phrases_vec):
    mp = {}
    remap = {}
    id = 0
    phrases = []
    for phrase, vec in phrases_vec.items():
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

            if(perfect_match(vi,vj) == 1):
                mp[pj] = mp[pi]
                remap[mp[pi]].append(pj)
    
    return mp, remap


if __name__ == "__main__":
    root_path = extract.get_root_path()
    tested_paths = []
    tested_paths.append(root_path + '/data/raw/complaints & use of force/Champaign IL Police Complaints/Investigations_Redacted.pdf')
    tested_paths.append(root_path + '/data/raw/complaints & use of force/UIUC PD Use of Force/22-274.releasable.pdf')
    tested_paths.append(root_path + '/data/raw/certification/CT/DecertifiedOfficersRev_9622 Emilie Munson.pdf')
    tested_paths.append(root_path + '/data/raw/certification/IA/Active_Employment.pdf')
    tested_paths.append(root_path + '/data/raw/certification/MT/RptEmpRstrDetail Active.pdf')
    tested_paths.append(root_path + '/data/raw/certification/VT/Invisible Institue Report.pdf')

    id = 0
    tested_id = 2 #starting from 1

    for path in tested_paths:
        id += 1
        # if(id != tested_id):
        #     continue
        #print(path)
        extracted_path = get_extracted_path(path)
        #print(extracted_path)
        phrases = get_relative_locations(extracted_path)
        out_path = get_relative_location_path(extracted_path)
        phrases = read_dict(out_path)
        perfect_align_clustering(phrases)
        