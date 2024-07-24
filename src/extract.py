from datetime import datetime
import pytesseract
import pdfplumber
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


def extract_algorithm(pdf_path, x_tolerance=3, y_tolerance=3):
    phrases = []
    page_break = 0
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            if page_break == 25:
                break 
            words = page.extract_words(x_tolerance=x_tolerance, y_tolerance=y_tolerance, extra_attrs=['size'])
            """
            If no words are extracted, then we apply OCR -> prone to manual changes 
            """
            current_phrase = []
            if not words: 
                # Convert PDF page to image
                # images = convert_from_path(pdf_path, first_page=page.page_number, last_page=page.page_number)
                # if images:
                #     # Extract text from the first (and only) image
                #     extracted_text = extract_text_from_image(images[0])
                #     # Correct the extracted text
                #     corrected_text = correct_words(extracted_text)
                #     # Split corrected text into phrases based on punctuation and new lines
                #     phrases.extend(corrected_text.split('\n'))
                # continue  # Skip to the next page
                return "This pdf is image-based or contains no selectable text." 
            else: 
                current_phrase = [words[0]['text']]
                for prev, word in zip(words, words[1:]):
                    """
                    Phrase Logic:
                    1. word['top'] == prev['top'] ==  This checks if the current word is exactly aligned with the previous word (prev) vertically. \
                        The 'top' attribute represents the vertical position of the top of the bounding box of each word.
                    2. abs(word['top'] - prev['top']) < y_tolerance == Even if they're not exactly aligned, this checks if they are close enough vertically within the y_tolerance. \
                        This accounts for slight differences in the vertical positioning that might occur due to the typesetting of the document.
                    3. abs(word['x0'] - prev['x1']) < x_tolerance == This checks if the horizontal space between the end of the previous word (prev['x1']) and the start of the current word (word['x0']) is less than or equal to x_tolerance. \
                        This would mean the words are close enough horizontally to be considered part of the same phrase.
                    4. word['x0'] < prev['x1'] ==  This condition checks for cases where the bounding box of the current word might overlap with the bounding box of the previous word, \
                        which can happen due to the irregularities in character spacing.
                    
                    word['top'] - word['bottom'] == prev['top'] - prev['bottom'] and 
                    word['top'] == prev['top'] and 
                    abs(word['top'] - prev['top']) < y_tolerance):

                    
                    """
                    is_header_cond = is_header(word['size'], threshold=12)
                    if is_header_cond:
                        continue
                    elif  (
                        ((word['top'] == prev['top'] or word['bottom'] == prev['bottom'])) 
                        and abs(word['x0'] - prev['x1']) < x_tolerance
                        ):
                    
                        # Words are on the same line and close to each other horizontally
                        current_phrase.append(word['text'])
                    else:
                        # New line or too far apart horizontally
                        phrases.append(' '.join(current_phrase))
                        current_phrase = [word['text']]
            phrases.append(' '.join(current_phrase))  # Append the last phrase
            page_break += 1
    return phrases

def extract_algorithm_v3(pdf_path, x_tolerance=3, y_tolerance=3):
    phrases = {}
    page_break = 0
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(x_tolerance=x_tolerance, y_tolerance=y_tolerance, extra_attrs=['size'])
            if not words:
                return "This pdf is image-based or contains no selectable text."
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
                if phrase_text in phrases:
                    phrases[phrase_text].append(tuple(current_bbox))
                else:
                    phrases[phrase_text] = [tuple(current_bbox)]
            if page_break == 19:
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
            key_with_colon = before_colon + ':'
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

    return adjusted_phrases_with_boxes

if __name__ == "__main__":
    #test

    raw_root_path = '/Users/yiminglin/Documents/Codebase/Dataset/pdf_reverse/'
    pdf_path = raw_root_path + 'complaints & use of force/UIUC PD Use of Force/22-274.releasable.pdf'
    phrases = extract_algorithm_v3(pdf_path)
    for p, bb in phrases.items():
        print(p)
