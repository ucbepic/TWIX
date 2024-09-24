#this script implements the evaluation metric 
import json,os

def read_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data 
    
def get_leaf_nodes_paris(data):
    #this function get the key-val pairs in all leaves per record 
    kvs_record = {} #record id -> a list of kvs 
    for record in data:
        id = record['id']
        content = record['content']
        kvs = []
        for block in content:
            #print(block['type'])
            for tuple in block['content']:
                #print(tuple)
                for k,v in tuple.items():
                    kvs.append((k,v))
        kvs_record[id] = kvs
    return kvs_record

def clean_phrase(p):
    if(isinstance(p,str)):
        return p.lower().strip()
    return p

def get_PR(results_kvs, truth_kvs):
    precisions = {} #record id ->  precision 
    recalls = {} # record id -> recall
    for id, truth_kv in truth_kvs.items():
        precision = 0
        recall = 0
        if id not in results_kvs:
            precisions[id] = 0
            recalls[id] = 0
            continue
        result_kv = results_kvs[id]

        #clean phrases in results and truths
        new_truth_kv = []
        new_result_kv = []
        for kv in truth_kv:
            new_truth_kv.append((clean_phrase(kv[0]), clean_phrase(kv[1])))
        for kv in result_kv:
            new_result_kv.append((clean_phrase(kv[0]), clean_phrase(kv[1])))

        # print(new_truth_kv)
        # print(new_result_kv)
        
        #evaluate precision
        for kv in new_result_kv:
            if(kv in new_truth_kv):
                precision += 1
        
        precision /= len(new_result_kv)

        #evaluate recall
        for kv in new_truth_kv:
            if kv in new_result_kv:
                recall += 1
        
        recall /= len(new_truth_kv)

        precisions[id] = precision
        recalls[id] = recall 
    
    #compute the average 
    avg_precision = 0
    avg_recall = 0
    for id, precision in precisions.items():
        avg_precision += precision
    avg_precision /= len(precisions)
    for id, recall in recalls.items():
        avg_recall += recall
    avg_recall /= len(recalls)

    return avg_precision, avg_recall, precisions, recalls

def scan_folder(path):
    file_names = []
    for root, dirs, files in os.walk(path):
        for file in files:
            file_name = os.path.join(root, file)
            if('DS_Store' in file_name):
                continue
            if('.json' not in file_name):
                continue
            file_names.append(file_name)
    return file_names

def get_result_path(truth_path):
    result_path = ''
    result_path = truth_path.replace('')
    return result_path

if __name__ == "__main__":
    truth_path = '/Users/yiminglin/Documents/Codebase/Pdf_reverse/data/truths/key_value_truth/complaints & use of force/Champaign IL Police Complaints/investigations.json'
    result_path = '/Users/yiminglin/Documents/Codebase/Pdf_reverse/result/complaints & use of force/Champaign IL Police Complaints/Investigations_Redacted__kv.json'

    result = read_json(result_path)
    truth = read_json(truth_path)

    result_kvs = get_leaf_nodes_paris(result)
    truth_kvs = get_leaf_nodes_paris(truth)

    avg_precision, avg_recall, precisions, recalls = get_PR(result_kvs, truth_kvs)
    print(precisions)
    print(recalls)


    