import sys
import key,eval,time
sys.path.append('/Users/yiminglin/Documents/Codebase/Pdf_reverse/')
from model import model 
model_name = 'gpt4o'

def LLM_text(phrases, path):
    instruction = 'The following list contains keys and values extracted from a document, return all the keys seperated by |. Do not generate duplicated keys. Do not make up new keys.'
    delimiter = ', '
    context = delimiter.join(phrases)
    prompt = (instruction,context)
    response = model(model_name,prompt)
    #print(response)
    l = response.split('|')
    key.write_result(path, l)

def LLM_table_extraction(phrases, path):
    instruction = 'The following list contains keys and values extracted from a table, return the table. The first row is a set of keys, the following rows are the values corresponding to the keys, seperate keys and values by using comma. '
    delimiter = ', '
    context = delimiter.join(phrases)
    prompt = (instruction,context)
    response = model(model_name,prompt)
    #print(response)
    #l = response.split('|')
    key.write_result(path, response)

def LLM_KV_extraction(phrases, path):
    instruction = 'The following list contains keys and values extracted from a document, find all the keys and their corresponding values. In each line, return a key and its value. Do not generate duplicated keys. Do not make up new keys.'
    delimiter = ', '
    context = delimiter.join(phrases)
    #print(context)
    prompt = (instruction,context)
    response = model(model_name,prompt)
    #print(response)
    key.write_result(path, response)

if __name__ == "__main__":

    root_path = '/Users/yiminglin/Documents/Codebase/Pdf_reverse'
    tested_paths = []
    tested_paths.append(root_path + '/data/raw/complaints & use of force/Champaign IL Police Complaints/Investigations_Redacted.pdf')
    tested_paths.append(root_path + '/data/raw/complaints & use of force/UIUC PD Use of Force/22-274.releasable.pdf')
    tested_paths.append(root_path + '/data/raw/certification/CT/DecertifiedOfficersRev_9622 Emilie Munson.pdf')
    tested_paths.append(root_path + '/data/raw/certification/IA/Active_Employment.pdf')
    tested_paths.append(root_path + '/data/raw/certification/MT/RptEmpRstrDetail Active.pdf')
    tested_paths.append(root_path + '/data/raw/certification/VT/Invisible Institue Report.pdf')

    test_lst = [1]
    
    for tested_id in range(len(tested_paths)):

        if(tested_id not in test_lst):
            continue
        print(tested_id)
        t1 = time.time()
        path = tested_paths[tested_id]
        print(path)
        name = 'LLM_' + model_name + '_kv'
        result_path = key.get_baseline_result_path(path,name)
        truth_path = key.get_truth_path(path,1)
        extracted_path = key.get_extracted_path(path)

        phrases = eval.read_file(extracted_path)
        #LLM_text(phrases, result_path)
        LLM_KV_extraction(phrases, result_path)
        t2 = time.time()
        print(t2-t1)
    