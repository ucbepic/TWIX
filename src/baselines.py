import sys
import key
sys.path.append('/Users/yiminglin/Documents/Codebase/Pdf_reverse/')
from model import model 
model_name = 'gpt4o'

def LLM_text(phrases, path):
    instruction = 'The following list contains keys and values extracted from a document, return all the keys seperated by |. '
    delimiter = ', '
    context = delimiter.join(phrases)
    prompt = (instruction,context)
    response = model(model_name,prompt)
    l = response.split('|')
    key.write_result(path, l)
    