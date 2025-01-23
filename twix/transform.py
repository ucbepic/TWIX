from . import key, pattern, extract
import os 
    
#This is end-to-end APIs that directly extract data from raw documents
def transform(pdf_paths, result_folder_path = ''):
    phrases = extract.extract_phrase(pdf_paths, result_path=result_folder_path)
    fields = key.predict_field(pdf_paths, result_folder=result_folder_path)
    template = pattern.predict_template(pdf_paths, result_folder=result_folder_path)
    extraction_objects = pattern.extract_data(pdf_paths, result_folder=result_folder_path)
    return fields, template, extraction_objects

    

