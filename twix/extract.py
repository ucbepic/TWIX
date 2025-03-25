from datetime import datetime
import pytesseract
import pdfplumber
import os 
import json
import pandas as pd
from PIL import Image
from pdf2image import convert_from_path
import os
import time 
from PyPDF2 import PdfMerger
import sys 
import csv
import math
import random
import logging
from collections import defaultdict
current_path = os.path.abspath(os.path.dirname(__file__))
root_path = os.path.abspath(os.path.join(current_path, os.pardir))
sys.path.append(root_path)
from twix.model import model 

vision_model_name = 'gpt4vision'

def get_image_path(target_folder):
    paths = []
    path = target_folder + '_image/0.jpg'
    paths.append(path)
    path = target_folder + '_image/1.jpg'
    paths.append(path)
    return paths


def extract_phrase_LLM(data_files, result_folder = ''):
    if(len(result_folder) == 0):
        result_folder = get_result_folder_path(data_files)

    image_paths = get_image_path(result_folder)

    prompt = 'Extract all raw phrases from the given images. A phrase is either a keyword, a value from key-value pairs, or an entry in a table, or random passage, like the footer, header or the title of table. Ensure the extracted phrases have NO duplicates. Return the phrases in reading order. Make sure all keywords must be returned. Separate each phrase with “|” and provide no additional explanations.' 
    
    response = model(vision_model_name,prompt,image_paths)
    #print(response)

    fields = [phrase.strip() for phrase in response.split('|')]
    #print(fields) 
    return fields 

def is_valid_time(time_str):
    try:
        datetime.strptime(time_str, '%I:%M%p')
        return True
    except ValueError:
        return False
    
def is_header(font_size, threshold=12):
    """Simple heuristic to determine if a text is a header based on font size."""
    return font_size > threshold

def extract_text_from_image(image):
    """Extracts text from a single image using pytesseract."""
    text = pytesseract.image_to_string(image)
    return text

def phrase_extract_pdfplumber_new(pdf_path, x_tolerance=3, y_tolerance=3, page_limit = 5):
    #print(page_limit)
    phrases = {}
    page_break = 0
    raw_phrases = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:#scan each page 
            words = page.extract_words(x_tolerance=x_tolerance, y_tolerance=y_tolerance, extra_attrs=['size'])
            if not words:
                print("This pdf is image-based or contains no selectable text.")
                return {},[]
            else:
                current_phrase = [words[0]['text']]
                # Initialize bounding box for the current phrase
                current_bbox = [words[0]['x0'], words[0]['top'], words[0]['x1'], words[0]['bottom'], page_break]
                lst_bbox = []
                lst_bbox.append(tuple(current_bbox))
                
                for prev, word in zip(words, words[1:]):
                    is_header_cond = is_header(word['size'], threshold=12)  # Assuming is_header is defined elsewhere
                    if is_header_cond:
                        continue
                    elif (
                        ((word['top'] == prev['top'] or word['bottom'] == prev['bottom'])) 
                        and abs(word['x0'] - prev['x1']) < 3
                    ):
                        # Words are on the same line and close to each other horizontally
                        current_phrase.append(word['text'])
                        lst_bbox.append((word['x0'],word['top'],word['x1'],word['bottom'],page_break))
                        # Update bounding box for the current phrase
                        current_bbox = [
                            min(current_bbox[0], word['x0']),
                            min(current_bbox[1], word['top']),
                            max(current_bbox[2], word['x1']),
                            max(current_bbox[3], word['bottom']),page_break
                        ]
                    else:
                        phrase_text = ' '.join(current_phrase)
                        raw_phrases.append(phrase_text)
                        
                        ad_phrases, bbx = adjust_phrase_rules(phrase_text, lst_bbox)
                        for i in range(len(ad_phrases)):
                            p = ad_phrases[i]
                            if(len(p) == 0):
                                continue
                            if p in phrases:
                                if(len(bbx) == 0):
                                    phrases[p].append(tuple(current_bbox))
                                else:
                                    phrases[p].append(tuple(bbx[i]))
                            else:
                                if(len(bbx) == 0):
                                    phrases[p] = [tuple(current_bbox)]
                                else:
                                    phrases[p] = [tuple(bbx[i])]
                        # Reset for the next phrase
                        current_phrase = [word['text']]
                        current_bbox = [word['x0'], word['top'], word['x1'], word['bottom'],page_break]
                        lst_bbox = [tuple(current_bbox)]
                
                # Append the last phrase and its bounding box
                # phrases[' '.join(current_phrase)] = current_bbox
                phrase_text = ' '.join(current_phrase)
                raw_phrases.append(phrase_text)

                ad_phrases, bbx = adjust_phrase_rules(phrase_text, lst_bbox)
                for i in range(len(ad_phrases)):
                    p = ad_phrases[i]
                    if(len(p) == 0):
                        continue
                    if p in phrases:
                        if(len(bbx) == 0):
                            phrases[p].append(tuple(current_bbox))
                        else:
                            phrases[p].append(tuple(bbx[i]))
                    else:
                        if(len(bbx) == 0):
                            phrases[p] = [tuple(current_bbox)]
                        else:
                            phrases[p] = [tuple(bbx[i])]
            if page_break == page_limit:
                break
            page_break += 1

    return phrases, raw_phrases



def adjust_phrase_plumber(phrase):
    if not is_valid_time(phrase) and phrase.count(':') == 1:
        before_colon, after_colon = phrase.split(':')
        return [before_colon, after_colon]
    else:
        return [phrase]
    

def adjust_phrase_rules(phrase, lst):
    if not is_valid_time(phrase) and phrase.count(':') == 1:
        if('Courtesy:' in phrase):
            return [phrase],[]
        before_colon, after_colon = phrase.split(':')
        #print(phrase)
        return [before_colon, after_colon],[]
    elif(phrase.count(':') == 0):
        if('Date AssignedRacialCategory / Type' in phrase):
            return ['Date Assigned', 'Racial', 'Category / Type'],[lst[0],lst[1],lst[2]]
        if('Disposition Completed Recorded On Camera' in phrase):
            return ['Disposition', 'Completed', 'Recorded On Camera'],[lst[0],lst[1],lst[2]]
        if('F/PAction' in phrase):
            print(lst)
            return ['F/P','Action'],[lst[0],lst[1]]
        return [phrase], []
    elif(phrase.count(':') == 2):
        #special case
        if('Action' in phrase and 'Date' in phrase):
            split_phrases = phrase.split("Action:")

            # Reformatting the second phrase
            split_phrases = [split_phrases[0].strip(), f"Action: {split_phrases[1].strip()}"]
            ps = []
            before_colon, after_colon = split_phrases[0].split(':')
            ps.append(before_colon)
            ps.append(after_colon)
            before_colon, after_colon = split_phrases[1].split(':')
            ps.append(before_colon)
            ps.append(after_colon)
            return ps,[]
    return [phrase],[]

def print_all_document_paths(folder_path):
    paths = []
    # Define the document file extensions you want to include
    document_extensions = ['.txt', '.pdf']

    # Walk through the directory tree
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if any(file.endswith(ext) for ext in document_extensions):
                # Construct the full file path
                file_path = os.path.join(root, file)
                paths.append(file_path)
    return paths

def get_all_pdf_paths(folder_path):
    pdf_paths = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.pdf'):
                pdf_paths.append(os.path.join(root, file))
    return pdf_paths

def get_root_path():
    current_path = os.path.abspath(os.path.dirname(__file__))
    parent_path = os.path.abspath(os.path.join(current_path, os.pardir))
    #print("Parent path:", parent_path)
    return parent_path

def get_text_path(raw_path, mode, approach):
    text_path = raw_path.replace('raw','extracted')
    text_path = text_path.replace('.pdf', '_' + approach + mode)
    return text_path

def write_phrase(path, phrases):
    out = ''
    for phrase in phrases:
        out += phrase
        out += '\n'
    with open(path, 'w') as file:
    # Write the string to the file
        file.write(out)

def write_dict(path, d):
    with open(path, 'w') as json_file:
        json.dump(d, json_file)

def get_result_folder_path(data_files):
    # Extract file names without extensions
    file_names = [path.split('/')[-1].split('.')[0] for path in data_files]

    # Join the names with an underscore and add .txt extension
    output_folder_name = '_'.join(file_names)
    root_path = get_root_path()
    path = root_path + '/tests/out/' + output_folder_name + '/'

    return path

def get_file_name(data_file):
    return os.path.splitext(os.path.basename(data_file))[0]

def merge_pdf(data_files, path):
    # Suppress PyPDF2 logging
    logging.getLogger("PyPDF2").setLevel(logging.ERROR)

    # Sort the files alphabetically by their file names
    pdf_files_sorted = sorted(data_files, key=lambda x: os.path.basename(x))

    # Create a PdfMerger object
    merger = PdfMerger()

    # Iterate through the sorted list and append each PDF to the merger
    for pdf in pdf_files_sorted:
        merger.append(pdf)

    # Define the output file path
    output_pdf = "merged.pdf"

    out_path = path + output_pdf

    # Write the merged PDF to the output file
    merger.write(out_path)
    merger.close()

    return out_path

def extract_phrase_one_doc(pdf_path, text_path, dict_path, page_limit):
    phrases, raw_phrases = phrase_extract_pdfplumber_new(pdf_path, page_limit = page_limit)
    adjusted_phrases = []
    for phrase in raw_phrases:
        adjusted_phrase,bbx = adjust_phrase_rules(phrase, [[],[],[]])
        for p in adjusted_phrase:
            if(len(p) == 0):
                continue
            adjusted_phrases.append(p)
    
    write_phrase(text_path, adjusted_phrases)
    write_dict(dict_path, phrases)

    return adjusted_phrases, phrases

def extract_phrase(data_files, result_folder = '', page_limit = 5):
    print('Phrase extraction starts...')
    if(len(result_folder) == 0):
        result_folder = get_result_folder_path(data_files)

    # Create the folder if it does not exist
    if not os.path.exists(result_folder):
        os.makedirs(result_folder)
    
    # merge pdfs into one
    merged_pdf_path = merge_pdf(data_files, result_folder)
    
    text_path = result_folder + 'merged_phrases.txt' 
    dict_path = result_folder + 'merged_phrases_bounding_box_page_number.json' 
    raw_path = result_folder  + 'merged_raw_phrases_bounding_box_page_number.txt' 
    
    #get image path
    image_foler = result_folder + '_image/'
    if not os.path.exists(image_foler):
        # Create the folder
        os.makedirs(image_foler)
    
    pdf_2_image(merged_pdf_path, 2, image_foler)
    
    #get ground_phrases_full
    phrase_LLM_path = get_phrase_LLM_path(data_files)
    ground_phrases_full = extract_phrase_LLM(data_files)
    write_phrase(phrase_LLM_path, ground_phrases_full)

    # extract prhases for merged pdfs
    phrases, phrases_bounding_box_page_number = extract_phrase_one_doc_v1(merged_pdf_path, text_path, dict_path, raw_path, data_files, page_limit)

    

    phrases_out = {}

    phrases_out['merged_data_files'] = (phrases, phrases_bounding_box_page_number)
    max_page_limit = 1000000

    for data_file in data_files:
        file_name = get_file_name(data_file)
        text_path = result_folder + file_name + '_phrases.txt'
        dict_path = result_folder + file_name + '_bounding_box_page_number.json' 
        raw_path = result_folder + file_name + '_raw_phrases_bounding_box_page_number.txt'
        #print(data_file)
        phrases, phrases_bounding_box_page_number = extract_phrase_one_doc_v1(data_file, text_path, dict_path, raw_path, data_files, max_page_limit) #extract all data for each document 
        phrases_out[file_name] = (phrases, phrases_bounding_box_page_number)

    #clean intermediate files 
    delete_file(phrase_LLM_path)
    return phrases_out

def extract_phrase_folders(data_folder, page_limit = 6, result_folder = ''):
    paths = print_all_document_paths(data_folder)
    for path in paths:

        st = time.time()
    
        print(path)
        text_path = get_text_path(path, '.txt', 'test_plumber')
        dict_path = get_text_path(path, '.json','test_plumber')

        print(text_path)
        print(dict_path)

        phrases, raw_phrases = phrase_extract_pdfplumber_new(path, page_limit=page_limit)
        adjusted_phrases = []
        for phrase in raw_phrases:
            adjusted_phrase,bbx = adjust_phrase_rules(phrase, [[],[],[]])
            for p in adjusted_phrase:
                if(len(p) == 0):
                    continue
                adjusted_phrases.append(p)

        et = time.time()
        print(et-st)
        write_phrase(text_path, adjusted_phrases)
        write_dict(dict_path, phrases)

def get_img(file_path):
    return bytearray(open(file_path, 'rb').read())

def get_text_from_path(file_path, client):
    img = get_img(file_path)
    return client.detect_document_text(
        Document={'Bytes':img}
    )

def get_lines(image, blocks):
    # Returns all blocks that are lines within a scanned text object.

    lines = []
    width, height = image.width, image.height
    for block in blocks:
        if block['BlockType'] != 'LINE':
            continue
        coords = []
        for coord_map in block['Geometry']['Polygon']:
            coords.append([coord_map['X']*width, coord_map['Y']*height])
        coords = coords[0] + coords[2]
        lines.append([block['Text'], coords])

    return lines    


def pdf_2_image(path, page_num, out_folder):
    images = convert_from_path(path, first_page = 1, last_page = page_num)
    size = min(page_num, len(images))
    for i in range(size):
        out_path = out_folder + str(i) + '.jpg'
        images[i] = images[i].save(out_path)
    return images

def create_folder(folder_path): 

    # Check if the folder exists, if not, create it
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"Folder '{folder_path}' created successfully.")
    else:
        print(f"Folder '{folder_path}' already exists.")

def create_images_pipeline(raw_folder, number_of_pages):
    #create images per page in a given range for all pdfs in the specified folder 
    paths = print_all_document_paths(raw_folder)
    for path in paths:
        print(path)
        # if('releasable' not in path):
        #     continue
        text_path = get_text_path(path, '.txt', '')
        image_folder_path = text_path.replace('.txt','image/')

        #print(text_path)
        #print(dict_path)
        print(image_folder_path)
        create_folder(image_folder_path)
        pdf_2_image(path,number_of_pages,image_folder_path)


### Version 2 of phrase extraction 
    
def get_pdf(path):
    return pdfplumber.open(path)

def extract_words(path, page_indices=list(range(5)), page_annot=True):
    pdf = get_pdf(path)
    words = []
    for page_index in page_indices:
        page = pdf.pages[page_index]
        page_words = page.extract_words(split_at_punctuation=':')
        if page_annot:
            for word in page_words:
                word['page'] = page_index+1
                word['size'] = (word['x1']-word['x0'])/len(word['text'])
        words.extend(page_words)
    return words

def display_words(path, page_index=0):
    page = get_pdf(path).pages[page_index]
    #display(page.to_image().draw_rects(page.extract_words())) # viewable in Jupyter Notebook.

#extract_words(file_path)
#display_words(file_path)

#
### F2: Obtain phrases.
# Here I implement two methods, dynamic seems more effective.

def get_phrases_manual(words, x_thresh = 6, y_thresh=4):
    """
    Groups words into phrases based on the following rules:
        (1) Each word in a phrase must be at most {x_thresh} away from the next word to right in phrase. (Compare x1 to x0)
        (2) First word in a phrase must be at most {y_thresh} away from any word in phrase. (Compare y_mid to y_mid, y_mid = (top + bottom)/2)
    """
    phrases = []
    cur_phrase = words[0]
    phrase_y_mid = (cur_phrase['bottom'] + cur_phrase['top']) / 2
    key_detected = False
    for word in words[1:]:

        # For K-V detection.
        if word['text'] == ':':
            key_detected = True
            continue

        word_y_mid = (word['top'] + word['bottom']) / 2
        if (not key_detected) and (word['x0'] - cur_phrase['x1'] <= x_thresh) and (abs(phrase_y_mid - word_y_mid) < y_thresh):
            cur_phrase['text'] += (' ' + word['text'])
            cur_phrase['x1'] = word['x1']
        else:
            key_detected = False
            phrases.append(cur_phrase)
            cur_phrase = word
            phrase_y_mid = (cur_phrase['bottom'] + cur_phrase['top']) / 2

    return phrases

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

def merge_three_phrases(phrase_a, phrase_b, phrase_c):
    """
    Merge three horizontally aligned phrases into one phrase with updated bounding box.
    
    Each input phrase dictionary is assumed to have these keys:
        {
            'text': str,
            'x0': float,
            'top': float,    # was y0
            'x1': float,
            'bottom': float, # was y1
            'page': int
        }

    The merged phrase will be:
        {
            'text': <concatenated string of the 3 texts>,
            'x0': <min x0 of the 3>,
            'top': <min top of the 3>,
            'x1': <max x1 of the 3>,
            'bottom': <max bottom of the 3>,
            'page': <common page>
        }

    Raises ValueError if the three phrases are not on the same page.
    """
    # 1) Check that all three are on the same page
    page_nums = {phrase_a['page'], phrase_b['page'], phrase_c['page']}
    if len(page_nums) != 1:
        raise ValueError("All three phrases must be on the same page to merge.")

    # 2) Merge text
    merged_text = " ".join([phrase_a['text'], phrase_b['text'], phrase_c['text']])

    # 3) Merge bounding box
    min_x0 = min(phrase_a['x0'], phrase_b['x0'], phrase_c['x0'])
    min_top = min(phrase_a['top'], phrase_b['top'], phrase_c['top'])
    max_x1 = max(phrase_a['x1'], phrase_b['x1'], phrase_c['x1'])
    max_bottom = max(phrase_a['bottom'], phrase_b['bottom'], phrase_c['bottom'])

    # 4) Construct the merged phrase
    merged_phrase = {
        'text': merged_text,
        'x0': min_x0,
        'top': min_top,
        'x1': max_x1,
        'bottom': max_bottom,
        'page': phrase_a['page']  # (all three share the same page)
    }
    return merged_phrase

def get_phrases_dynamic_v1(words, y_thresh=4):
    """
    Recall that size is equal to (x1 - x0) / len(word).
    For phrase p and word w, define a character having size (p_size + w_size) / 2.
    Groups words into phrases based on the following rules:
        (1) Each word in a phrase must be at most {one character} away from the next word to right in phrase. (Compare x1 to x0)
        (2) First word in a phrase must be at most {y_thresh} away from any word in phrase. (Compare y_mid to y_mid, y_mid = (top + bottom)/2)
    """
    phrases = []
    cur_phrase = words[0]#this is previous phrase 
    phrase_y_mid = (cur_phrase['bottom'] + cur_phrase['top']) / 2
    key_detected = False
    is_merge = False
    detected = False
    i = 1
    while i < len(words):
        word = words[i]

        if word['text'] == ':':
            detected = True
            if(i < len(words)-1 and is_number(words[i-1]['text']) and is_number(words[i+1]['text'])):
                is_merge = True
            elif(i < len(words)-1 and is_number(words[i-1]['text']) and ('am' in words[i+1]['text'].lower() or 'pm' in words[i+1]['text'].lower() )): 
                is_merge = True
            else:
                key_detected = True
            #print(words[i-1]['text'],words[i+1]['text'],is_merge, key_detected)
            
        if(is_merge and detected):#merge phrases 
            new_phrase = merge_three_phrases(words[i-1], words[i], words[i+1])
            phrases.append(new_phrase)
            is_merge = False
            i += 2
            cur_phrase = words[i-1]
        else: 
            if(detected and key_detected):
                key_detected = False
                phrases.append(cur_phrase)
                cur_phrase = word
                phrase_y_mid = (cur_phrase['bottom'] + cur_phrase['top']) / 2
                i += 1
            else:
                word_y_mid = (word['top'] + word['bottom']) / 2
                char_size = (cur_phrase['size'] + word['size']) / 2
                if (not key_detected) and (word['x0'] - cur_phrase['x1'] <= char_size) and (abs(phrase_y_mid - word_y_mid) < y_thresh):#merge two phrases
                    cur_phrase['text'] += (' ' + word['text'])
                    cur_phrase['x1'] = word['x1']
                    cur_phrase['size'] = word['size']
                
            i += 1

    return phrases

def get_phrases_dynamic(words, y_thresh=4):
    """
    Recall that size is equal to (x1 - x0) / len(word).
    For phrase p and word w, define a character having size (p_size + w_size) / 2.
    Groups words into phrases based on the following rules:
        (1) Each word in a phrase must be at most {one character} away from the next word to right in phrase. (Compare x1 to x0)
        (2) First word in a phrase must be at most {y_thresh} away from any word in phrase. (Compare y_mid to y_mid, y_mid = (top + bottom)/2)
    """
    phrases = []
    cur_phrase = words[0]
    phrase_y_mid = (cur_phrase['bottom'] + cur_phrase['top']) / 2
    key_detected = False
    for i in range(1,len(words)):
        word = words[i]

        if word['text'] == ':':
            print(words[i-1]['text'], words[i+1]['text'])
            key_detected = True
            continue

        word_y_mid = (word['top'] + word['bottom']) / 2
        char_size = (cur_phrase['size'] + word['size']) / 2
        if (not key_detected) and (word['x0'] - cur_phrase['x1'] <= char_size) and (abs(phrase_y_mid - word_y_mid) < y_thresh):
            cur_phrase['text'] += (' ' + word['text'])
            cur_phrase['x1'] = word['x1']
            cur_phrase['size'] = word['size'] # current phrase inherits the new word's size for the next comparison.
        else:
            key_detected = False
            phrases.append(cur_phrase)
            cur_phrase = word
            phrase_y_mid = (cur_phrase['bottom'] + cur_phrase['top']) / 2

    return phrases

def get_phrases_csv(path, user_page_indices=list(range(5))):
    pdf = get_pdf(path)
    actual_page_indices = list(range(0, len(get_pdf(path).pages)))
    page_indices = min([user_page_indices, actual_page_indices], key=len)

    words = extract_words(path, page_indices)
    phrases = get_phrases_dynamic(words)

    phrases_list = []
    for phrase in phrases:
        phrases_list.append([phrase['text'], phrase['x0'], phrase['top'], phrase['x1'], phrase['bottom'], phrase['page']])

    phrases_df = pd.DataFrame(phrases_list, columns=['text', 'x0', 'y0', 'x1', 'y1', 'page'])
    return phrases_df

def write_csv(file_path,data):
    data.to_csv(file_path, index=False)

def extract_phrase_one_doc_v1(in_path, text_path, dict_path, raw_path, data_files, page_count): 
    user_page_indices = list(range(page_count))
    print('Processing ', in_path)
    print('Word extraction starts...')
    #1 first pass extraction 
    #get raw_phrases_bounding_box_page_number
    raw_phrases_bounding_box_page_number = get_phrases_csv(in_path, user_page_indices)
    
    write_csv(raw_path, raw_phrases_bounding_box_page_number)

    print('Learn rules for word concatation...')
    #2 learn rules
    distance_threshold, max_pos_dist, ground_phrases_full, ground_phrases_sub = learn_rules(raw_path, data_files)

    #3 apply rules 
    raw_phases = load_extracted_words(raw_path)
    refined_phrases = apply_rules(raw_phases, distance_threshold, max_pos_dist, ground_phrases_full, ground_phrases_sub)

    print('Refine phases extraction based on learned rules...')
    #4 get phrase only list
    phrases_txt = [phrase for phrase in refined_phrases['text'].values.tolist() if type(phrase) == str]

    #5 get phrase bounding box vector 
    phrases_json = {}
    for label, group in refined_phrases.groupby("text", sort=False):
        phrases_json[label] = group.iloc[:, 1:].values.tolist()

    write_phrase(text_path, phrases_txt)
    write_dict(dict_path, phrases_json)

    #clean intermediate files 
    #delete_file(raw_path)
    
    return phrases_txt, phrases_json

def get_phrase_LLM_path(pdf_paths):
    result_folder_path = get_result_folder_path(pdf_paths)
    return result_folder_path + 'phrases_LLM.txt'

def read_file(file):
    data = []
    with open(file, 'r') as file:
        # Iterate over each line in the file
        for line in file:
            # Print the line (you can replace this with other processing logic)
            data.append(line.strip())
    return data


def learn_rules(raw_phrases_with_bounding_box_path, pdf_paths):
    #load raw phrases and raw phrases with LLMs 
    phrases = load_extracted_words(raw_phrases_with_bounding_box_path)
    phrase_LLM_path = get_phrase_LLM_path(pdf_paths)
    ground_phrases_full = load_ground_truth_phrases(phrase_LLM_path)
    ground_phrases_full = list(set(ground_phrases_full))
    ground_phrases_sub = build_subphrase_set(ground_phrases_full)


    positive_pairs, negative_pairs = build_pairs_optimized(phrases, ground_phrases_full, ground_phrases_sub)

    # print('positive pairs:')
    # print(positive_pairs)

    # print('negative pairs:')
    # print(negative_pairs)

    #Choose a distance threshold
    max_pos_dist, min_neg_dist = find_distance_threshold(positive_pairs, negative_pairs)

    delta = 0.001
    distance_threshold = min(min_neg_dist-delta, (max_pos_dist+min_neg_dist)/2) 

    return distance_threshold, max_pos_dist, ground_phrases_full, ground_phrases_sub
    
    return df 

def apply_rules(phrases, distance_threshold, max_pos_dist, ground_phrases_full, ground_phrases_sub):
    if(distance_threshold < 0):
        merged_phrases = merge_words_if_ground_phrase(phrases, ground_phrases_full, ground_phrases_sub)
    elif(distance_threshold > max_pos_dist): 
        merged_phrases = merge_words_with_stop_condition(phrases, distance_threshold)
    else:
        merged_phrases = merge_words_if_ground_phrase(phrases, ground_phrases_full, ground_phrases_sub)

    df = pd.DataFrame(merged_phrases, columns=['text','x0','y0','x1','y1','page'])

    return df 

def delete_file(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)

    
def load_extracted_words(filepath):
    """
    Reads raw words from a CSV-like text file that starts with a header:
        text,x0,y0,x1,y1,page
    Each subsequent line is a single extracted word and its bounding box plus page.
    Example line:
        Order #,38.016,41.249,61.746,48.249,1
    Returns a list of dicts, each with keys:
        text, x0, y0, x1, y1, page
    """
    words = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # skip the header line
        for row in reader:
            # row is [text, x0, y0, x1, y1, page]
            text = row[0].strip()  # normalized text
            x0, y0, x1, y1 = map(float, row[1:5])
            page = int(row[5])
            words.append({
                'text': text,
                'x0': x0,
                'y0': y0,
                'x1': x1,
                'y1': y1,
                'page': page
            })
    return words

def load_ground_truth_phrases(filepath):
    """
    Reads one phrase per line, lowercases and strips whitespace.
    Returns a set of full ground-truth phrases.
    """
    phrases = set()
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            phrase = line.strip()
            if phrase:
                phrases.add(phrase)
    return phrases

def horizontally_overlaps(w1, w2, min_overlap_ratio=0.2):
    """
    Returns True if w1 and w2 share the same page and have some horizontal overlap.
    We define overlap in x-dimension, and require that overlap
    be at least min_overlap_ratio * min(width1, width2).
    """
    if w1['page'] != w2['page']:
        return False
    overlap = min(w1['x1'], w2['x1']) - max(w1['x0'], w2['x0'])
    if overlap <= 0:
        return False
    width1 = w1['x1'] - w1['x0']
    width2 = w2['x1'] - w2['x0']
    return overlap >= min_overlap_ratio * min(width1, width2)

def vertical_distance(w1, w2):
    """
    A simple measure of vertical gap: the distance between w1's lower edge and w2's upper edge
    (or vice versa if w2 is on top).
    """

    if w1['page'] != w2['page']:
        return math.inf
    
    if w2['y0'] >= w1['y1']:
        # w2 is below w1
        return w2['y0'] - w1['y1']
    elif w1['y0'] >= w2['y1']:
        # w1 is below w2
        return w1['y0'] - w2['y1']
    else:
        # They overlap vertically; effectively distance is 0
        return 0.0

def build_pairs_optimized(words, ground_phrases_full, ground_phrases_sub):
    """
    1) Group words by page and sort them top->bottom.
    2) For each word w_i, find the next word w_j that horizontally overlaps.
    3) If w_i is a full ground-truth phrase, (w_i, w_j) => negative pair.
    4) Else if w_i + " " + w_j is in ground_phrases_sub, => positive pair.
    5) Otherwise => negative pair.
    """
    page_map = defaultdict(list)
    for w in words:
        page_map[w['page']].append(w)

    # Sort each page's list top->bottom, left->right
    # for pg in page_map:
    #     page_map[pg].sort(key=lambda w: (w['y0'], w['x0']))

    positive_pairs = []
    negative_pairs = []

    for pg, word_list in page_map.items():
        n = len(word_list)
        for i, w_i in enumerate(word_list):
            w_i_text = w_i['text']
            # find next horizontally overlapping word
            chosen_j = None
            for j in range(i+1, n):
                w_j = word_list[j]
                if horizontally_overlaps(w_i, w_j):
                    chosen_j = w_j
                    break  # only take the first
            if chosen_j:
                pair_dist = vertical_distance(w_i, chosen_j)
                w_j_text = chosen_j['text']

                # 1) if w_i_text alone is a FULL phrase => negative
                if w_i_text in ground_phrases_full:
                    negative_pairs.append((w_i_text, w_j_text, pair_dist))
                else:
                    # 2) else if w_i_text + w_j_text is in sub-phrases => positive
                    concat = w_i_text + " " + w_j_text
                    if concat in ground_phrases_sub:
                        positive_pairs.append((w_i_text, w_j_text, pair_dist))
                    else:
                        negative_pairs.append((w_i_text, w_j_text, pair_dist))

    return positive_pairs, negative_pairs

def build_subphrase_set(ground_phrases):
    """
    For each multi-word phrase in ground_phrases,
    generate all possible consecutive sub-phrases (from length 1 to full length).
    Return a set containing all of them.
    Example:
        "start date time" => 
           "start", "date", "time",
           "start date", "date time",
           "start date time"
    """
    subphrase_set = set()
    for phrase in ground_phrases:
        tokens = phrase.split()
        # Generate all consecutive sub-phrases of any length
        for start_idx in range(len(tokens)):
            for end_idx in range(start_idx + 1, len(tokens) + 1):
                sub = " ".join(tokens[start_idx:end_idx])
                subphrase_set.add(sub)
    return subphrase_set


def sample_negative_pairs(negative_pairs, max_samples=50):
    """
    Randomly sample from negative pairs if we have too many.
    """
    if len(negative_pairs) <= max_samples:
        return negative_pairs
    return random.sample(negative_pairs, max_samples)

def find_distance_threshold(positive_pairs, negative_pairs):
    """
    Use the maximum distance among positive pairs and the minimum distance
    among negative pairs. Return the midpoint of these two values as a threshold.
    """
    if not positive_pairs or not negative_pairs:
        return -1,-1
    
    # max distance among positive pairs
    max_pos_dist = max(dist for (_, _, dist) in positive_pairs)
    
    # min distance among negative pairs
    min_neg_dist = min(dist for (_, _, dist) in negative_pairs)
    
    # midpoint
    return max_pos_dist, min_neg_dist


def merge_words_with_stop_condition(words, distance_threshold):
    """
    Merge consecutive *vertically aligned* words if each next word:
      - is on the same page,
      - horizontally overlaps,
      - has vertical distance <= distance_threshold
    Stop merging as soon as we encounter a gap > distance_threshold.
    
    Steps:
      1) Sort words by (page, y0, x0).
      2) For each un-merged word i (anchor):
         a) Mark it used; create a merged phrase from it.
         b) Scan subsequent words j = i+1..n-1:
            - skip any already used
            - if not horizontally aligned, skip (look further)
            - if distance <= threshold, merge j (update bounding box, text)
            - else distance > threshold => break
         c) Append the final merged phrase to output.
      3) Return the new list of merged phrases in reading order.
    
    The returned list uses the same dict structure as the input:
      {'text', 'x0', 'y0', 'x1', 'y1', 'page'}
    """
    # 1) Sort in reading order
    sorted_words = sorted(words, key=lambda w: (w['page'], w['y0'], w['x0']))
    
    used = [False] * len(sorted_words)
    merged_phrases = []
    n = len(sorted_words)
    
    for i in range(n):
        if used[i]:
            # Already merged with a previous anchor
            continue
        
        # Start a new merged phrase from word i
        anchor = sorted_words[i]
        used[i] = True
        
        merged_text = anchor['text']
        min_x0 = anchor['x0']
        min_y0 = anchor['y0']
        max_x1 = anchor['x1']
        max_y1 = anchor['y1']
        current_page = anchor['page']
        
        # We'll compare distance to the *last* merged word's bounding box
        last_word_box = {
            'page': current_page,
            'x0': min_x0,
            'y0': min_y0,
            'x1': max_x1,
            'y1': max_y1
        }
        
        # 2) Search further down for the *next* vertically aligned word
        j = i + 1
        while j < n:
            if used[j]:
                j += 1
                continue
            
            candidate = sorted_words[j]
            # must be same page
            if candidate['page'] != current_page:
                # Different page => definitely stop
                break
            
            # Check horizontal overlap with the last merged word's bounding box
            if not horizontally_overlaps(last_word_box, candidate):
                # Not the next "vertically aligned" word => skip it
                j += 1
                continue
            
            # Now check vertical distance
            dist = vertical_distance(last_word_box, candidate)
            if dist <= distance_threshold:
                # Merge
                used[j] = True
                merged_text += " " + candidate['text']
                
                # Update bounding box
                min_x0 = min(min_x0, candidate['x0'])
                min_y0 = min(min_y0, candidate['y0'])
                max_x1 = max(max_x1, candidate['x1'])
                max_y1 = max(max_y1, candidate['y1'])
                
                # Update last_word_box
                last_word_box = {
                    'page': current_page,
                    'x0': min_x0,
                    'y0': min_y0,
                    'x1': max_x1,
                    'y1': max_y1
                }
                
                j += 1
            else:
                # We encountered a bigger gap -> STOP searching further for this anchor
                break
        
        # Add the merged phrase
        merged_phrases.append({
            'text': merged_text,
            'x0': min_x0,
            'y0': min_y0,
            'x1': max_x1,
            'y1': max_y1,
            'page': current_page
        })

    return merged_phrases

def merge_words_if_ground_phrase(words, ground_phrases, ground_phrases_sub):
    """
    1) Sort words by (page, y0, x0).
    2) For each un-merged word (anchor), build up a merged phrase by 
       trying to append the *next* vertically aligned word IF the 
       new concatenation is in ground_phrases.
    3) If adding the next word does NOT form a valid ground phrase, stop merging.
    4) Return a list of merged (or single) phrases, each with updated bounding box.
    """

    # Sort the input words in reading order
    # sorted_words = sorted(words, key=lambda w: (w['page'], w['y0'], w['x0']))
    sorted_words = words
    n = len(sorted_words)
    used = [False]*n

    merged_phrases = []

    # Helper to update bounding box
    def update_bbox(bbox, w):
        bbox['x0'] = min(bbox['x0'], w['x0'])
        bbox['y0'] = min(bbox['y0'], w['y0'])
        bbox['x1'] = max(bbox['x1'], w['x1'])
        bbox['y1'] = max(bbox['y1'], w['y1'])

    for i in range(n):
        if used[i]:
            continue
        
        # Start a new phrase from word i
        anchor = sorted_words[i]
        used[i] = True
        
        # The concatenated text so far
        current_text = anchor['text']
        
        # Initialize bounding box with anchor's box
        merged_box = {
            'page': anchor['page'],
            'x0': anchor['x0'],
            'y0': anchor['y0'],
            'x1': anchor['x1'],
            'y1': anchor['y1']
        }

        j = i + 1
        while j < n:
            if used[j]:
                j += 1
                continue
            
            candidate = sorted_words[j]
            # Must be same page and horizontally overlap
            if candidate['page'] == merged_box['page'] and horizontally_overlaps(merged_box, candidate):
                # Construct the new concatenation
                new_text = current_text + " " + candidate['text']
                # Check if new_text is in ground_phrases
                if new_text in ground_phrases_sub or new_text in ground_phrases:
                    # Merge candidate
                    used[j] = True
                    current_text = new_text
                    update_bbox(merged_box, candidate)
                    j += 1
                    # Keep trying to merge the next word
                    continue
                else:
                    # new_text not in ground_phrases => stop
                    break
            elif(candidate['page'] != merged_box['page']):
                break
            else:
                j += 1
                continue

        # At this point, we finalize the current phrase
        merged_phrases.append({
            'text': current_text,
            'x0': merged_box['x0'],
            'y0': merged_box['y0'],
            'x1': merged_box['x1'],
            'y1': merged_box['y1'],
            'page': merged_box['page']
        })

    return merged_phrases


def phrase_extraction_try(path, page_annot=True):
    result_folder = get_result_folder_path(path)
    merged_path = result_folder + 'merged.pdf'
    page_count = 5
    user_page_indices = list(range(page_count))
    raw_phrases_bounding_box_page_number = get_phrases_csv(merged_path, user_page_indices)
    write_csv(result_folder + 'test.csv', raw_phrases_bounding_box_page_number)

if __name__ == "__main__":
    print(root_path)
    pdf_paths = []
    pdf_paths.append(root_path + '/tests/data/Investigations_Redacted_original.pdf') 
    extract_phrase(pdf_paths) 