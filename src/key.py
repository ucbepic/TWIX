import json
import extract

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

def get_extracted_path(path):
    path = path.replace('raw','extracted')
    path = path.replace('.pdf','.txt')
    return path

def get_relative_location_path(extracted_path):
    path = extracted_path[:-4] + '_relative_location.csv'
    return path

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
        #print(out_path)
        write_dict(out_path, phrases)