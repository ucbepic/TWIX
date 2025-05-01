from . import key, pattern, extract
import os 
    
#This is end-to-end APIs that directly extract data from raw documents
def transform(pdf_paths, result_folder_path, LLM_model_name, vision_feature = False):
    total_cost = 0
    phrases, cost = extract.extract_phrase(pdf_paths, result_folder_path, LLM_model_name=LLM_model_name, vision_feature=vision_feature)
    total_cost += cost 
    fields, cost = key.predict_field(pdf_paths, result_folder_path, LLM_model_name=LLM_model_name)
    total_cost += cost 
    template, cost = pattern.predict_template(pdf_paths, result_folder_path, LLM_model_name=LLM_model_name)
    total_cost += cost 
    extraction_objects, cost = pattern.extract_data(pdf_paths, result_folder_path)
    total_cost += cost 
    return fields, template, extraction_objects, cost 

    

