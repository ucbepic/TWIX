import key

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

def filter(truths, phrases):
    l = []
    for v in truths:
        if(v not in phrases):
            print('True key not in the extracted text: '+v)
        else:
            l.append(v)

    return l

def eval(truths, results):
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
    print(len(results), precision)
    print(len(truths), recall)
    precision = precision / len(results)
    recall = recall / len(truths)

    return precision, recall, FP, FN

if __name__ == "__main__":
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
        result_path = key.get_baseline_result_path(path,'textLLM_gpt4')
        truth_path = key.get_truth_path(path,1)
        extracted_path = key.get_extracted_path(path)

        phrases = format(read_file(extracted_path))
        truths = format(read_file(truth_path))
        results = format(read_file(result_path))
        
        truths = filter(truths, phrases)
        precision, recall, FP, FN = eval(truths, results)
        print(precision,recall)
        #break