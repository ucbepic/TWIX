import sys
import key,eval
sys.path.append('/Users/yiminglin/Documents/Codebase/Pdf_reverse/')
from model import model 
model_name = 'gpt4'

def LLM_text(phrases, path):
    instruction = 'The following list contains keys and values extracted from a document, return all the keys seperated by |. Do not generate duplicated keys. Do not make up new keys.'
    delimiter = ', '
    context = delimiter.join(phrases)
    prompt = (instruction,context)
    response = model(model_name,prompt)
    #print(response)
    l = response.split('|')
    key.write_result(path, l)

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
        result_path = key.get_baseline_result_path(path,'textLLM_gpt4')
        truth_path = key.get_truth_path(path,1)
        extracted_path = key.get_extracted_path(path)

        phrases = eval.read_file(extracted_path)
        LLM_text(phrases, result_path)
    