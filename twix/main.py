from . import key, pattern, extract
import os 

def scan_folder(path, filter_file_type = '.pdf'):
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
    
def transform():
    root_path = extract.get_root_path()
    #print(root_path)
    pdf_folder_path = root_path + '/data/raw'
    print(pdf_folder_path)
    pdfs = scan_folder(pdf_folder_path,'.pdf')
    for pdf_path in pdfs:
        if 'Invisible Institue Report' not in pdf_path:
            continue

        print(pdf_path)

        #predict fields
        
        key.predict_field(pdf_path)
        #predict the template and extract data
        out_path = key.get_key_val_path(pdf_path, 'TWIX')
        
        
        # #print(image_path)
        pattern.extract_data(pdf_path, out_path)

if __name__ == "__main__":
    transform()
    

