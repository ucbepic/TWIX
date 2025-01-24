import twix
import os 

def get_root_path():
    current_path = os.path.abspath(os.path.dirname(__file__))
    parent_path = os.path.abspath(os.path.join(current_path, os.pardir))
    return parent_path

if __name__ == "__main__":
    root_path = get_root_path()
    pdf_paths = []
    pdf_paths.append(root_path + '/tests/data/DecertifiedOfficersRev_9622 Emilie Munson.pdf')

    # new_fields = ["2022"]
    # fields = twix.add_fields(new_fields, data_files=pdf_paths)

    # deleted_fields = ["2022"]
    # fields = twix.remove_fields(deleted_fields, data_files=pdf_paths)

    #print(fields)

    # twix.modify_template_node(0,'kv',["2022"], data_files=pdf_paths)
    # twix.remove_template_node([0],data_files=pdf_paths)
    

