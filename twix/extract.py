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

def phrase_extract_pdfplumber_new(pdf_path, x_tolerance=2, y_tolerance=2, page_limit = 10):
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


# def phrase_extract_pdfplumber(pdf_path, x_tolerance=3, y_tolerance=3, page_limit = 10):
#     phrases = {}
#     page_break = 0
#     raw_phrases = []
#     with pdfplumber.open(pdf_path) as pdf:
#         for page in pdf.pages:
#             words = page.extract_words(x_tolerance=x_tolerance, y_tolerance=y_tolerance, extra_attrs=['size'])
#             if not words:
#                 print("This pdf is image-based or contains no selectable text.")
#                 return {},[]
#             else:
#                 current_phrase = [words[0]['text']]
#                 # Initialize bounding box for the current phrase
#                 current_bbox = [words[0]['x0'], words[0]['top'], words[0]['x1'], words[0]['bottom'], page_break]
                
#                 for prev, word in zip(words, words[1:]):
#                     is_header_cond = is_header(word['size'], threshold=12)  # Assuming is_header is defined elsewhere
#                     if is_header_cond:
#                         continue
#                     elif (
#                         ((word['top'] == prev['top'] or word['bottom'] == prev['bottom'])) 
#                         and abs(word['x0'] - prev['x1']) < 3
#                     ):
#                         # Words are on the same line and close to each other horizontally
#                         current_phrase.append(word['text'])
#                         # Update bounding box for the current phrase
#                         current_bbox = [
#                             min(current_bbox[0], word['x0']),
#                             min(current_bbox[1], word['top']),
#                             max(current_bbox[2], word['x1']),
#                             max(current_bbox[3], word['bottom']),page_break
#                         ]
#                     else:
#                         phrase_text = ' '.join(current_phrase)
#                         raw_phrases.append(phrase_text)
                        
#                         ad_phrases, bbx = adjust_phrase_rules(phrase_text)
#                         for i in range(len(ad_phrases)):
#                             p = ad_phrases[i]
#                             if(len(p) == 0):
#                                 continue
#                             if p in phrases:
#                                 phrases[p].append(tuple(current_bbox))
#                             else:
#                                 phrases[p] = [tuple(current_bbox)]
#                         # Reset for the next phrase
#                         current_phrase = [word['text']]
#                         current_bbox = [word['x0'], word['top'], word['x1'], word['bottom'],page_break]
                
#                 # Append the last phrase and its bounding box
#                 # phrases[' '.join(current_phrase)] = current_bbox
#                 phrase_text = ' '.join(current_phrase)
#                 raw_phrases.append(phrase_text)

#                 ad_phrases = adjust_phrase_rules(phrase_text)
#                 for p in ad_phrases:
#                     if(len(p) == 0):
#                         continue
#                     if p in phrases:
#                         phrases[p].append(tuple(current_bbox))
#                     else:
#                         phrases[p] = [tuple(current_bbox)]
#             if page_break == page_limit:
#                 break
#             page_break += 1

#     return phrases, raw_phrases


    

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
    # Sort the files alphabetically by their file names
    pdf_files_sorted = sorted(data_files, key=lambda x: os.path.basename(x))

    # Create a PdfMerger object
    merger = PdfMerger()

    # Iterate through the sorted list and append each PDF to the merger
    for pdf in pdf_files_sorted:
        merger.append(pdf)

    # Define the output file path
    output_pdf = "merged_output.pdf"

    out_path = path + output_pdf

    # Write the merged PDF to the output file
    merger.write(out_path)
    merger.close()

def extract_phrase_one_doc(data_file, text_path, dict_path, page_limit):
    phrases, raw_phrases = phrase_extract_pdfplumber_new(data_file, page_limit)
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

def extract_phrase(data_files, result_path = '', page_limit = 5):
    if(len(result_path) == 0):
        result_path = get_result_folder_path(data_files)

    # Create the folder if it does not exist
    if not os.path.exists(result_path):
        os.makedirs(result_path)

    # merge pdfs into one
    merged_pdf = merge_pdf(data_files, result_path)

    text_path = result_path + 'merged_phrases.txt' 
    dict_path = result_path + 'merged_phrases_bounding_box_page_number.json' 

    # extract prhases for merged pdfs
    phrases, phrases_bounding_box_page_number = extract_phrase_one_doc(merged_pdf, text_path, dict_path, page_limit)

    phrases_out = {}

    phrases_out['merged_data_files'] = (phrases, phrases_bounding_box_page_number)

    for data_file in data_files:
        file_name = get_file_name(data_file)
        text_path = result_path + file_name + '_phrases.txt'
        dict_path = result_path + file_name + '_bounding_box_page_number.json' 
        phrases, phrases_bounding_box_page_number = extract_phrase_one_doc(data_file, text_path, dict_path, page_limit)
        phrases_out[file_name] = (phrases, phrases_bounding_box_page_number)

    return phrases_out





def extract_phrase_folders(data_folder, page_limit = 6, result_path = ''):
    paths = print_all_document_paths(data_folder)
    for path in paths:
        
        # if('Active_Employment' not in path):
        #     continue

        st = time.time()
    
        print(path)
        text_path = get_text_path(path, '.txt', 'test_plumber')
        dict_path = get_text_path(path, '.json','test_plumber')

        print(text_path)
        print(dict_path)

        phrases, raw_phrases = phrase_extract_pdfplumber_new(path, page_limit)
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

def phrase_extraction_aws(image_folder_path, num_pages, client):
    #the first output is phrases+bounding box: phrase, list of its bounding box 
    #the second output is the raw_phrases in reading order 
    doc_lines = []
    raw_phrases = []
    phrase_bb = {}
    for page in range(num_pages):
        file_path = image_folder_path + str(page)+'.jpg'
        #print(file_path)
        spec_image = Image.open(file_path)
        text = get_text_from_path(file_path, client)
        lines = get_lines(spec_image, text['Blocks'])
        lines = [[page+1]+line for line in lines]
        doc_lines += lines
        #print(lines)
        #break
    for line in doc_lines:
        #print(line)
        phrase = line[1]
        #process phrases
        adjusted_phrase = adjust_phrase_rules(phrase)
        bb = line[2]
        #print(adjusted_phrase)
        for p in adjusted_phrase:
            if(p == ''):
                continue
            raw_phrases.append(p)
            if(p not in phrase_bb):
                phrase_bb[p] = [bb]
            else:
                phrase_bb[p].append(bb)


    return raw_phrases, phrase_bb
        #print(line)


    


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

def phrase_extraction_pipeline_aws(raw_folder):
    print(raw_folder)
    client = load_file_keys_aws()
    paths = print_all_document_paths(raw_folder)
    for path in paths:
        print(path)
        # if('releasable' not in path):
        #     continue
        text_path = get_text_path(path, '.txt', 'aws')
        dict_path = get_text_path(path, '.json', 'aws')
        image_folder_path = text_path.replace('.txt','_image/')

        print(text_path)
        print(dict_path)
        page_number = 6
        
        raw_phrases, phrase_bb = phrase_extraction_aws(image_folder_path, page_number, client)
        write_phrase(text_path, raw_phrases)
        write_dict(dict_path, phrase_bb)
        #break
        
    
    #pdf_2_image(file_path,number_of_pages,out_folder_path)
    # doc_lines = get_doc_lines(out_folder_path, number_of_pages)
    # doc_lines_df = pd.DataFrame(doc_lines, columns=['Page', 'Phrase', 'x1', 'y1', 'x2', 'y2'])
    # doc_lines_df.to_csv(file_name+'.csv')


if __name__ == "__main__":
    root_path = get_root_path()
    data_folder = root_path + '/data/raw/certification'
    page_limit = 6 #number of page for data extraction
    
    #create_images_pipeline(data_folder,6)
    extract_phrase(data_folder)

    
    

    
