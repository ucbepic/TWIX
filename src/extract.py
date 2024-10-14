from datetime import datetime
import pytesseract
import pdfplumber
import os 
import json
import boto3
import pandas as pd
from PIL import Image, ImageDraw
from pdf2image import convert_from_path
import os
import key 


"""
When extracting text from pdf documnet, we aim for a particular format. 
Each sentence in the PDF should start on a new line, maintaining consistent spacing between phrases. 
This consistency is important for the next step in the pipeline, which is to convert the text into a structured format.

"""
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


def phrase_extract_pdfplumber(pdf_path, x_tolerance=3, y_tolerance=3, page_limit = 10):
    phrases = {}
    page_break = 0
    raw_phrases = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(x_tolerance=x_tolerance, y_tolerance=y_tolerance, extra_attrs=['size'])
            if not words:
                print("This pdf is image-based or contains no selectable text.")
                return {},[]
            else:
                current_phrase = [words[0]['text']]
                # Initialize bounding box for the current phrase
                current_bbox = [words[0]['x0'], words[0]['top'], words[0]['x1'], words[0]['bottom']]
                
                for prev, word in zip(words, words[1:]):
                    is_header_cond = is_header(word['size'], threshold=12)  # Assuming is_header is defined elsewhere
                    if is_header_cond:
                        continue
                    elif (
                        ((word['top'] == prev['top'] or word['bottom'] == prev['bottom'])) 
                        and abs(word['x0'] - prev['x1']) < x_tolerance
                    ):
                        # Words are on the same line and close to each other horizontally
                        current_phrase.append(word['text'])
                        # Update bounding box for the current phrase
                        current_bbox = [
                            min(current_bbox[0], word['x0']),
                            min(current_bbox[1], word['top']),
                            max(current_bbox[2], word['x1']),
                            max(current_bbox[3], word['bottom'])
                        ]
                    else:
                        phrase_text = ' '.join(current_phrase)
                        raw_phrases.append(phrase_text)
                        
                        ad_phrases = adjust_phrase_plumber(phrase_text)
                        for p in ad_phrases:
                            if(len(p) == 0):
                                continue
                            if p in phrases:
                                phrases[p].append(tuple(current_bbox))
                            else:
                                phrases[p] = [tuple(current_bbox)]
                        # Reset for the next phrase
                        current_phrase = [word['text']]
                        current_bbox = [word['x0'], word['top'], word['x1'], word['bottom']]
                
                # Append the last phrase and its bounding box
                # phrases[' '.join(current_phrase)] = current_bbox
                phrase_text = ' '.join(current_phrase)
                raw_phrases.append(phrase_text)

                ad_phrases = adjust_phrase_plumber(phrase_text)
                for p in ad_phrases:
                    if(len(p) == 0):
                        continue
                    if p in phrases:
                        phrases[p].append(tuple(current_bbox))
                    else:
                        phrases[p] = [tuple(current_bbox)]
            if page_break == page_limit:
                break
            page_break += 1

    return phrases, raw_phrases
    

def phrase_extract(pdf_path, x_tolerance=3, y_tolerance=3, page_limit = 6):
    phrases = {}
    page_break = 0
    raw_phrases = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(x_tolerance=x_tolerance, y_tolerance=y_tolerance, extra_attrs=['size'])
            if not words:
                print("This pdf is image-based or contains no selectable text.")
                return {},[]
            else:
                current_phrase = [words[0]['text']]
                # Initialize bounding box for the current phrase
                current_bbox = [words[0]['x0'], words[0]['top'], words[0]['x1'], words[0]['bottom']]
                
                for prev, word in zip(words, words[1:]):
                    is_header_cond = is_header(word['size'], threshold=12)  # Assuming is_header is defined elsewhere
                    if is_header_cond:
                        continue
                    elif (
                        ((word['top'] == prev['top'] or word['bottom'] == prev['bottom'])) 
                        and abs(word['x0'] - prev['x1']) < x_tolerance
                    ):
                        # Words are on the same line and close to each other horizontally
                        current_phrase.append(word['text'])
                        # Update bounding box for the current phrase
                        current_bbox = [
                            min(current_bbox[0], word['x0']),
                            min(current_bbox[1], word['top']),
                            max(current_bbox[2], word['x1']),
                            max(current_bbox[3], word['bottom'])
                        ]
                    else:
                        # New line or too far apart horizontally, finalize current phrase
                        # phrases[' '.join(current_phrase)] = current_bbox
                        # current_phrase = [word['text']]
                        # current_bbox = [word['x0'], word['top'], word['x1'], word['bottom']]
                        # New line or too far apart horizontally, finalize current phrase
                        phrase_text = ' '.join(current_phrase)
                        raw_phrases.append(phrase_text)
                        
                        if phrase_text in phrases:
                            
                            # Phrase already exists, append the bounding box to the list of bounding boxes
                            #print(phrase_text, tuple(current_bbox))
                            phrases[phrase_text].append(tuple(current_bbox))
                        else:
                          
                            # Phrase does not exist, create a new list of bounding boxes
                            phrases[phrase_text] = [tuple(current_bbox)]
                        # Reset for the next phrase
                        current_phrase = [word['text']]
                        current_bbox = [word['x0'], word['top'], word['x1'], word['bottom']]
                
                # Append the last phrase and its bounding box
                # phrases[' '.join(current_phrase)] = current_bbox
                phrase_text = ' '.join(current_phrase)
                raw_phrases.append(phrase_text)
                if phrase_text in phrases:
                    phrases[phrase_text].append(tuple(current_bbox))
                else:
                    phrases[phrase_text] = [tuple(current_bbox)]
            if page_break == page_limit:
                break
            page_break += 1

    # c=0
    # for p,bb in phrases.items():
    #     print(p)
    #     for i in range(min(len(bb),10)):
    #         print(bb[i])
    #     print('')
    #     c+=1
    #     if(c>=80):
    #         break

    """
    Now take every phrase and split the colon values 
    """
    adjusted_phrases_with_boxes = {}
    c=0
    for phrase, bboxes_list in phrases.items():
        # print(phrase)
        # c+=1
        # if(c>=10):
        #     break
        if not is_valid_time(phrase) and phrase.count(':') == 1:
            before_colon, after_colon = phrase.split(':')
            # For the part before the colon, include the colon and append each bounding box to the list
            key_with_colon = before_colon
            if key_with_colon not in adjusted_phrases_with_boxes:
                adjusted_phrases_with_boxes[key_with_colon] = []
            
            # Extend the current list with the new bounding boxes
            adjusted_phrases_with_boxes[key_with_colon].extend(bboxes_list)
            
            # For the part after the colon, if it's not empty, append each bounding box to the list
            after_colon = after_colon.strip()
            if after_colon:
                if after_colon not in adjusted_phrases_with_boxes:
                    adjusted_phrases_with_boxes[after_colon] = []
                
                # Extend the current list with the new bounding boxes
                adjusted_phrases_with_boxes[after_colon].extend(bboxes_list)
        else:
            # No colon split required, just assign the list of bounding boxes
            if phrase in adjusted_phrases_with_boxes:
                adjusted_phrases_with_boxes[phrase].extend(bboxes_list)
            else:
                adjusted_phrases_with_boxes[phrase] = bboxes_list

    return adjusted_phrases_with_boxes, raw_phrases

def adjust_phrase_plumber(phrase):
    if not is_valid_time(phrase) and phrase.count(':') == 1:
        before_colon, after_colon = phrase.split(':')
        return [before_colon, after_colon]
    else:
        return [phrase]
    

def adjust_phrase_aws(phrase):
    if not is_valid_time(phrase) and phrase.count(':') == 1:
        if('Courtesy:' in phrase):
            return [phrase]
        before_colon, after_colon = phrase.split(':')
        #print(phrase)
        return [before_colon, after_colon]
    elif(phrase.count(':') == 0):
        if('Date Assigned Racial Category / Type' in phrase):
            return ['Date Assigned', 'Racial', 'Category / Type']
        if('Disposition Completed Recorded On Camera' in phrase):
            return ['Disposition', 'Completed', 'Recorded On Camera']
        return [phrase]
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
            return ps
    return [phrase]

def print_all_document_paths(folder_path):
    paths = []
    # Define the document file extensions you want to include
    document_extensions = ['.txt', '.pdf', '.doc', '.docx']

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

def get_text_path(raw_path, mode, approach = 'plumber'):
    text_path = raw_path.replace('raw','extracted')
    text_path = text_path.replace('.pdf','_' + approach + mode)
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

def phrase_extraction_pipeline_pdfplumber(data_folder, page_limit):
    paths = print_all_document_paths(data_folder)
    for path in paths:
        print(path)
        # if('releasable' not in path):
        #     continue
        text_path = get_text_path(path, '.txt')
        dict_path = get_text_path(path, '.json')
        phrases, raw_phrases = phrase_extract_pdfplumber(path, page_limit)
        adjusted_phrases = []
        for phrase in raw_phrases:
            adjusted_phrase = adjust_phrase_plumber(phrase)
            for p in adjusted_phrase:
                if(len(p) == 0):
                    continue
                adjusted_phrases.append(p)
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
        adjusted_phrase = adjust_phrase_aws(phrase)
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

def load_file_keys_aws():
    keys = pd.read_csv('/Users/yiminglin/Documents/Codebase/credentials/textract_accessKeys.csv')
    #load client
    client = boto3.client('textract',
                      region_name='us-west-1',
                      aws_access_key_id=keys.iloc[0]['Access key ID'],
                      aws_secret_access_key=keys.iloc[0]['Secret access key']
                     )
    return client



def create_folder(folder_path): 

    # Check if the folder exists, if not, create it
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"Folder '{folder_path}' created successfully.")
    else:
        print(f"Folder '{folder_path}' already exists.")

def create_images_pipeline(raw_folder):
    #create images per page in a given range for all pdfs in the specified folder 
    paths = print_all_document_paths(raw_folder)
    for path in paths:
        print(path)
        # if('releasable' not in path):
        #     continue
        text_path = get_text_path(path, '.txt', 'aws')
        dict_path = get_text_path(path, '.json', 'aws')
        image_folder_path = text_path.replace('.txt','_image/')

        #print(text_path)
        #print(dict_path)
        print(image_folder_path)
        number_of_pages = 15
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
    data_folder = root_path + '/data/raw/benchmark1/'
    page_limit = 20 #number of page for data extraction
    #write_texts_plumber(data_folder,page_limit)
    #phrase_extraction_pipeline_aws(data_folder)
    phrase_extraction_pipeline_pdfplumber(data_folder, page_limit)

    
