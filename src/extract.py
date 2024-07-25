from datetime import datetime
import pytesseract
import pdfplumber
import os 
import json
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


def phrase_extract(pdf_path, x_tolerance=3, y_tolerance=3):
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
                            phrases[phrase_text].append(tuple(current_bbox))
                        else:
                          
                            # Phrase does not exist, create a new list of bounding boxes
                            phrases[phrase_text] = [tuple(current_bbox)]
                        # Reset for the next phrase
                        current_phrase = [word['text']]
                        current_bbox = [page_break, word['x0'], word['top'], word['x1'], word['bottom']]
                
                # Append the last phrase and its bounding box
                # phrases[' '.join(current_phrase)] = current_bbox
                phrase_text = ' '.join(current_phrase)
                raw_phrases.append(phrase_text)
                if phrase_text in phrases:
                    phrases[phrase_text].append(tuple(current_bbox))
                else:
                    phrases[phrase_text] = [tuple(current_bbox)]
            if page_break == 6:
                break
            page_break += 1

    """
    Now take every phrase and split the colon values 
    """
    adjusted_phrases_with_boxes = {}
    for phrase, bboxes_list in phrases.items():
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

def adjust_phrase(phrase):
    if not is_valid_time(phrase) and phrase.count(':') == 1:
        before_colon, after_colon = phrase.split(':')
        return [before_colon, after_colon]
    else:
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
                #print(file_path)
                paths.append(file_path)
                # print(get_text_path(file_path))
                # print('')
    return paths

def get_root_path():
    current_path = os.path.abspath(os.path.dirname(__file__))
    parent_path = os.path.abspath(os.path.join(current_path, os.pardir))
    #print("Parent path:", parent_path)
    return parent_path

def get_text_path(raw_path, mode):
    text_path = raw_path.replace('raw','extracted')
    text_path = text_path.replace('.pdf',mode)
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

def write_texts(data_folder):
    paths = print_all_document_paths(data_folder)
    for path in paths:
        print(path)
        # if('22-274.releasable' not in path):
        #     continue
        text_path = get_text_path(path, '.txt')
        dict_path = get_text_path(path, '.json')
        phrases, raw_phrases = phrase_extract(path)
        adjusted_phrases = []
        for phrase in raw_phrases:
            adjusted_phrase = adjust_phrase(phrase)
            for p in adjusted_phrase:
                if(len(p) == 0):
                    continue
                adjusted_phrases.append(p)
        #print(phrases)
        #write phrase-only 
        write_phrase(text_path, adjusted_phrases)
        #write the complete dict 
        write_dict(dict_path, phrases)

        

if __name__ == "__main__":
    root_path = get_root_path()
    data_folder = root_path + '/data/raw'
    write_texts(data_folder)

    
