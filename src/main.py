import eval, key, pattern, baselines, extract
import os 
import argparse

def scan_folder(path, filter_file_type = '.json'):
    file_names = []
    for root, dirs, files in os.walk(path):
        for file in files:
            file_name = os.path.join(root, file)
            if('DS_Store' in file_name):
                continue
            if(filter_file_type not in file_name):
                continue
            file_names.append(file_name)
    return file_names
    

if __name__ == "__main__":
    root_path = extract.get_root_path()
    pdf_folder_path = root_path + '/data/raw'
    pdfs = scan_folder(pdf_folder_path,'.pdf')
    for pdf_path in pdfs:
        #if a dataset does not have ground truth, skip it
        truth_path = key.get_truth_path(pdf_path)

        if not os.path.exists(truth_path):
            continue

        print(pdf_path)
        # result_path = key.get_result_path(pdf_path)
        # if os.path.exists(result_path):
        #     continue

        # #predict fields
        key.key_prediction(pdf_path)
        #predict the template and extract data
        out_path = key.get_key_val_path(pdf_path, 'TWIX')
        pattern.kv_extraction(pdf_path, out_path)
