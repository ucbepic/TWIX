import twix
import os 

def get_root_path():
    current_path = os.path.abspath(os.path.dirname(__file__))
    parent_path = os.path.abspath(os.path.join(current_path, os.pardir))
    return parent_path

if __name__ == "__main__":
    root_path = get_root_path()
    pdf_paths = []
    pdf_paths.append(root_path + '/tests/data/Investigations_Redacted.pdf')

    #phrases = twix.extract_phrase(pdf_paths)
    fields = twix.predict_field(pdf_paths)
    

