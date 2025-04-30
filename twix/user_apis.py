#This script implements several user operations
from . import extract, key, pattern
import os 

def add_fields(added_fields, result_folder):
    if(len(result_folder) == 0):
        print('Add fields fails. Please specify data_files or result_folder. ')
        return 
    
    #read predicted fields
    key_path = key.get_key_path(result_folder)
    fields = key.read_file(key_path)

    #read extracted phrases 
    extracted_path = key.get_merged_extracted_path(result_folder)
    phrases = key.read_file(extracted_path)
    phrases = set(phrases)

    #check validity of added_fields
    phrases_low = []
    for p in phrases:
        phrases_low.append(p.lower())
    phrases_low = set(phrases_low)

    valid_fields = []
    for f in added_fields:
        if(f.lower() in phrases_low):
            valid_fields.append(f)
        else:
            print(f + ' is not found in the extracted phrases. Please check the spelling.')
    
    #update fields 
    for f in valid_fields:
        if(f not in fields):
            fields.append(f)
    
    #write the updated fields to local file 
    result_path = key.get_key_path(result_folder)
    key.write_result(result_path,fields)

    print('Fields are updated!')

    return fields


def remove_fields(removed_fields, result_folder):
    if(len(result_folder) == 0):
        print('Remove fields fails. Please speciify data files or result folders. ')
        return 
    
    #read predicted fields
    key_path = key.get_key_path(result_folder)
    fields = key.read_file(key_path)

    #read extracted phrases 
    extracted_path = key.get_merged_extracted_path(result_folder)
    phrases = key.read_file(extracted_path)
    phrases = set(phrases)

    #check validity of added_fields
    phrases_low = []
    for p in phrases:
        phrases_low.append(p.lower())
    phrases_low = set(phrases_low)

    valid_fields = []
    for f in removed_fields:
        if(f.lower() in phrases_low):
            valid_fields.append(f)
        else:
            print(f + ' is not found in the extracted phrases. Please check the spelling.')

    new_removed_fields = []

    for f in valid_fields:
        if(f not in fields):
            print(f + ' is not found in the predicted fields. Please check the spelling.')
        else:
            new_removed_fields.append(f)
    
    new_fields = []

    #update fields 
    for f in fields:
        if(f not in new_removed_fields):
            new_fields.append(f)
    
    #write the updated fields to local file 
    result_path = key.get_key_path(result_folder)
    key.write_result(result_path,new_fields)
    
    print('Fields are updated!')

    return new_fields

def remove_template_node(node_ids, result_folder):
    if(len(result_folder) == 0):
        print('Remove fields fails. Please speciify data files or result folders. ')
        return 

    #read template 
    template_path = key.get_template_path(result_folder)
    if os.path.isfile(template_path):
        template = pattern.read_template(template_path)
    else:
        print('Template does not exist in local directory.')
        return  
    
    updated_template = []
    for i in range(len(template)):
        if(i not in node_ids):
            updated_template.append(template[i])
    
    #write template to local directory
    #get template path
    template_path = key.get_template_path(result_folder)
    pattern.write_template(updated_template, template_path)

    print('Template is updated!')
    return updated_template

def modify_template_node(node_id, type, fields, result_folder):
    if(len(result_folder) == 0):
        print('Remove fields fails. Please speciify data files or result folders. ')
        return 

    #read template 
    template_path = key.get_template_path(result_folder)
    if os.path.isfile(template_path):
        template = pattern.read_template(template_path)
    else:
        print('Template does not exist in local directory.')
        return 

    new_template = []
    for i in range(len(template)):
        if(i != node_id):
            new_template.append(template)
        else:
            node = template[i]
            node['type'] = type
            node['fields'] = fields
            new_template.append(node)

    #write template to local directory
    #get template path
    template_path = key.get_template_path(result_folder)
    pattern.write_template(new_template, template_path)
    print('Template is updated!')

    return new_template

