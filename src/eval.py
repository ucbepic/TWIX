import key,os,csv

def read_file(file):
    data = []
    with open(file, 'r') as file:
        # Iterate over each line in the file
        for line in file:
            # Print the line (you can replace this with other processing logic)
            data.append(line.strip())
    return data

def format(lst):
    l = []
    for v in lst:
        l.append(v.lower().strip())
    return l

def format_key_val(lst):
    data = []
    for l in lst:
        r = l.split(',')
        if(r[0].lower() == 'key' and r[1].lower() == 'value'):
            continue
        data.append((r[0].lower().strip(),r[1].lower().strip(),r[2]))
    return data 

def filter(truths, phrases):
    l = []
    for v in truths:
        if(v not in phrases):
            print('True key not in the extracted text: '+v)
        else:
            l.append(v)

    return l

def eval_key(truths, results):
    precision = 0
    recall = 0
    FP = []
    FN = []
    for v in results:
        if(v not in truths):
            FP.append(v)
        else:
            precision += 1
    for v in truths:
        if(v not in results):
            FN.append(v)
        else:
            recall += 1
    # print(len(results), precision)
    # print(len(truths), recall)
    precision = precision / len(results)
    recall = recall / len(truths)

    return precision, recall, FP, FN


def eval_key_val(truths, results):
    page = '1.0'
    precision = 0
    recall = 0
    FP = []
    FN = []

    truth_size = 0
    for truth in truths:
        #print(type(truth[2]), type(page))
        if(truth[2] != page):
            continue
        truth_size += 1
        t = (truth[0],truth[1])
        is_match = 0
        for result in results:
            r = (result[0], result[1])
            if(t==r):
                recall += 1
                is_match = 1
                break
        if(is_match == 0):
            FN.append(t)
    
    for result in results:
        r = (result[0], result[1])
        is_match = 0
        for truth in truths:
            if(truth[2] != page):
                continue
            t = (truth[0],truth[1])
            if(t==r):
                precision += 1
                is_match = 1
                break
        if(is_match == 0):
            FP.append(r)
            
    precision /= len(results)
    recall /= truth_size

    return precision, recall, FP, FN


def get_truth_key_val_path(raw_path):
    path = raw_path.replace('raw','truths/key_value_truth')
    path = path.replace('.pdf','.csv')
    return path

def eval_key_procedure():
    root_path = '/Users/yiminglin/Documents/Codebase/Pdf_reverse'
    tested_paths = []
    tested_paths.append(root_path + '/data/raw/complaints & use of force/Champaign IL Police Complaints/Investigations_Redacted.pdf')
    tested_paths.append(root_path + '/data/raw/complaints & use of force/UIUC PD Use of Force/22-274.releasable.pdf')
    tested_paths.append(root_path + '/data/raw/certification/CT/DecertifiedOfficersRev_9622 Emilie Munson.pdf')
    tested_paths.append(root_path + '/data/raw/certification/IA/Active_Employment.pdf')
    tested_paths.append(root_path + '/data/raw/certification/MT/RptEmpRstrDetail Active.pdf')
    tested_paths.append(root_path + '/data/raw/certification/VT/Invisible Institue Report.pdf')


    for tested_id in range(len(tested_paths)):

        path = tested_paths[tested_id]
        print(path)
        #result_path = key.get_result_path(path)
        result_path = key.get_baseline_result_path(path,'clustering')
        truth_path = key.get_truth_path(path,1)
        extracted_path = key.get_extracted_path(path)

        phrases = format(read_file(extracted_path))
        truths = format(read_file(truth_path))
        results = format(read_file(result_path))
        
        truths = filter(truths, phrases)
        precision, recall, FP, FN = eval(truths, results)
        print(precision,recall)
        #break

def eval_key_val_procedure():
    root_path = '/Users/yiminglin/Documents/Codebase/Pdf_reverse'
    tested_paths = []
    tested_paths.append(root_path + '/data/raw/complaints & use of force/Champaign IL Police Complaints/Investigations_Redacted.pdf')
    tested_paths.append(root_path + '/data/raw/complaints & use of force/UIUC PD Use of Force/22-274.releasable.pdf')
    tested_paths.append(root_path + '/data/raw/certification/CT/DecertifiedOfficersRev_9622 Emilie Munson.pdf')
    tested_paths.append(root_path + '/data/raw/certification/IA/Active_Employment.pdf')
    tested_paths.append(root_path + '/data/raw/certification/MT/RptEmpRstrDetail Active.pdf')
    tested_paths.append(root_path + '/data/raw/certification/VT/Invisible Institue Report.pdf')

    tested_id = 1
    
    path = tested_paths[tested_id]
    print(path)
    result_path = key.get_key_val_path(path, 'partial')
    truth_path = get_truth_key_val_path(path)
    extracted_path = key.get_extracted_path(path)

    phrases = format(read_file(extracted_path))
    truths = format_key_val(read_file(truth_path))
    results = format_key_val(read_file(result_path))

    # for l in results:
    #     print(l)
    
    precision, recall, FP, FN = eval_key_val(truths, results)
    print(precision,recall)

    print('FP:')
    for fp in FP:
        print(fp)

    print('FN:')
    for fn in FN:
        print(fn)

if __name__ == "__main__":
    eval_key_val_procedure()