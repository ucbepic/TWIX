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

def format_key_val(dict):
    a=0

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

def read_csv(file):
    # Open the CSV file
    with open('filename.csv', mode='r', newline='') as file:
        # Create a CSV reader object
        reader = csv.reader(file)
        
        # Iterate over each row in the CSV file
        for row in reader:
            print(row)  # Each row is a list of values

def eval_key_val(truths, results):
    page = 1
    
def get_key_val_result_path(raw_path):
    path = raw_path.replace('data/raw','result')
    path = path.replace('.pdf', '_keyval.txt')
    return path

def get_truth_key_val_path(raw_path):
    path = raw_path.replace('raw','truths/key_value_truth')
    path = path.replace('.pdf','.txt')
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


    for tested_id in range(len(tested_paths)):

        path = tested_paths[tested_id]
        print(path)
        result_path = get_key_val_result_path(path)
        truth_path = get_truth_key_val_path(path,1)
        extracted_path = key.get_extracted_path(path)

        phrases = format(read_file(extracted_path))
        truths = format_key_val(read_csv(truth_path))
        results = format_key_val(read_csv(result_path))
        
        truths = filter(truths, phrases)
        precision, recall, FP, FN = eval_key_val(truths, results)
        print(precision,recall)

if __name__ == "__main__":
    eval_key_val_procedure()