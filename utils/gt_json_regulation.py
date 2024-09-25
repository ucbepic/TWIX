#this script translates the ground truth data into json format 
import pandas as pd
from io import StringIO
import json
import os 
import math 
def regulate_table(data):
    print('print raw data:')
    print(data)
    print("end of printing raw data")
    table_data = StringIO(data)
    # Read the CSV file into a pandas DataFrame
    df = pd.read_csv(table_data, index_col=False, quotechar='"', skipinitialspace=True)
    rows = []
    
    for index, row in df.iterrows():
        print('index:', index)
        print(row)
        row_object = {}
        for key,val in row.items():
            #print(key,val)
            # if(math.isnan(float(val))):
            #     print('val is null')
            if(isinstance(key, str)):
                key = key.strip()
            if(isinstance(val, str)):
                val = val.strip()
            row_object[key] = val
            
        rows.append(row_object)
    return rows
        
def regulate_kv(data):
    kvs_content = []
    kv_pairs = data.split('\n')
    for kv in kv_pairs:
        kvs = kv.split(',', 1)
        key = kvs[0]
        if(len(kvs) > 1):
            val = kvs[1]
        else:
            val = ''
        object = {}
        if(isinstance(key, str)):
                key = key.strip()
        if(isinstance(val, str)):
            val = val.strip()
        if(key == ''):
            continue
        #print(key,val)
        object[key] = val
        kvs_content.append(object)
        #print(key,val)
    return kvs_content 

def regulate_template(path):
    # Open the file in read mode
    records = []
    with open(path, 'r') as file:
        # Read line by line
        
        rid = 0
        record = {}
        object = []
        block = {}
        type = ''
        content = ''

        for line in file:
            line = line.strip()
            if('#Record' in line):
                
                #add previous record into records 
                if(len(record) > 0):
                    #add last block 
                    if(content != ''):
                        block['content'] = content
                        object.append(block)
                        #set up a new block
                        block = {}
                        content = ''
                    record['content'] = object
                    records.append(record)
                #initialie a new record and setup the record id
                rid = int(line[-1])
                record = {}
                record['id'] = rid
                object = []
            else:
                if('-TABLE' in line):
                    #add the processed block into object
                    if(content != ''):
                        block['content'] = content
                        object.append(block)
                    #set up a new block
                    block = {}
                    block['type'] = 'table'
                    type = 'table'
                    content = ''
                elif('-KV' in line):
                    #add the processed block into object
                    if(content != ''):
                        block['content'] = content
                        object.append(block)
                    #set up a new block
                    block = {}
                    block['type'] = 'kv'
                    type = 'kv'
                    content = ''
                else:
                    #process a row of data 
                    if(type == 'table'):
                        content += line + '\n'
                    else:
                        content += line + '\n'
        
        #last line, add last block and last records
        if(content != ''):
            block['content'] = content
            object.append(block)
        record['content'] = object
        records.append(record)

    return records 

def regular_full(records):
    new_records = []
    for record in records:
        print(record['id'])
        new_record = {}
        new_record['id'] = record['id']
        object = record['content']
        new_object = []
        for block in object:
            new_block = {}
            new_block['type'] = block['type']
            if(block['type'] == 'table'):
                content = regulate_table(block['content'])
            elif(block['type'] == 'kv'):
                content = regulate_kv(block['content'])
            new_block['content'] = content
            new_object.append(new_block)
        new_record['content'] = new_object
        new_records.append(new_record)
    return new_records
            
def write_json(out, path):
    with open(path, 'w') as json_file:
        json.dump(out, json_file, indent=4)

def scan_folder(path):
    file_names = []
    for root, dirs, files in os.walk(path):
        for file in files:
            file_name = os.path.join(root, file)
            if('DS_Store' in file_name):
                continue
            if('.txt' not in file_name):
                continue
            file_names.append(file_name)
    return file_names
            

if __name__ == "__main__":
    in_path = '/Users/yiminglin/Documents/Codebase/Pdf_reverse/data/truths/key_value_truth/complaints & use of force/Champaign IL Police Complaints/investigations.txt'
    out_path = '/Users/yiminglin/Documents/Codebase/Pdf_reverse/data/truths/key_value_truth/complaints & use of force/Champaign IL Police Complaints/investigations.json'

    folder_path = '/Users/yiminglin/Documents/Codebase/Pdf_reverse/data/truths/key_value_truth/'
    files = scan_folder(folder_path)
    for in_file in files:
        out_file = in_file.replace('txt','json')
        print(out_file)
        if('investigation' not in out_file):
            continue
        records = regulate_template(in_file)
        records = regular_full(records)
        write_json(records, out_file)
    


