from pdfminer.high_level import extract_text
from pdfminer.pdfpage import PDFPage
import pdfplumber
from datetime import datetime
import os 

def text_extract(in_path, k=1):
    text = []
    out = ''
    with pdfplumber.open(in_path) as pdf:
        for page_num in range(min(k, len(pdf.pages))):
            page = pdf.pages[page_num]
            # Extract the lines of text as a list
            lines = page.extract_text().split('\n')
            for line in lines:
                # Split the line into words
                words = line.split()
                line_str = ','.join(words)
                out += line_str + '\n'
                #text.append(words)
    return out
def is_valid_time(time_str):
    try:
        datetime.strptime(time_str, '%I:%M%p')
        return True
    except ValueError:
        return False
    
def is_header(font_size, threshold=12):
    """Simple heuristic to determine if a text is a header based on font size."""
    return font_size > threshold



def phrase_extract_v1(pdf_path, x_tolerance=3, y_tolerance=3, k=1):
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
                    else:
                        phrase_text = ' '.join(current_phrase)
                        raw_phrases.append(phrase_text)
                        
                        ad_phrases = adjust_phrase(phrase_text)
                        for p in ad_phrases:
                            if(len(p) == 0):
                                continue
                        # Reset for the next phrase
                        current_phrase = [word['text']]
                
                # Append the last phrase and its bounding box
                # phrases[' '.join(current_phrase)] = current_bbox
                phrase_text = ' '.join(current_phrase)
                raw_phrases.append(phrase_text)

                ad_phrases = adjust_phrase(phrase_text)
                for p in ad_phrases:
                    if(len(p) == 0):
                        continue
            if page_break == k:
                break
            page_break += 1

    return  raw_phrases

import pdfplumber

def phrase_extract_v2(pdf_path, x_tolerance=3, y_tolerance=3, k=1):
    page_break = 0
    raw_lines = []  # This will store lines of text
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(x_tolerance=x_tolerance, y_tolerance=y_tolerance, extra_attrs=['size'])
            if not words:
                print("This pdf is image-based or contains no selectable text.")
                return [], []
            else:
                current_line = [words[0]['text']]  # Start with the first word of the page
                
                for prev, word in zip(words, words[1:]):
                    is_header_cond = is_header(word['size'], threshold=12)  # Assuming is_header is defined elsewhere
                    if is_header_cond:
                        continue
                    # Check if the word belongs to the same line based on y-coordinates (top/bottom)
                    if (word['top'] == prev['top'] or word['bottom'] == prev['bottom']):
                        # Words are on the same line
                        current_line.append(word['text'])
                    else:
                        # If the word is on a different line, save the current line and start a new one
                        raw_lines.append(','.join(current_line))
                        current_line = [word['text']]
                
                # Append the last line for the page
                raw_lines.append(','.join(current_line))

            if page_break == k:  # Stop after processing the first k pages
                break
            page_break += 1

    return raw_lines  # Return lines of text


def adjust_phrase(phrase):
    if not is_valid_time(phrase) and phrase.count(':') == 1:
        before_colon, after_colon = phrase.split(':')
        return [before_colon, after_colon]
    else:
        return [phrase]

def store_string_to_file(s, filename):
    with open(filename, 'w') as file:
        file.write(s)

def pdf_2_text_pipeline(in_path, out_path,k=1):
    lines = phrase_extract_v2(in_path,k)
    out = ''
    for line in lines:
        #print(line)
        out += line + '\n'
    store_string_to_file(out, out_path)

if __name__ == "__main__":
    in_path = '/Users/yiminglin/Documents/Codebase/Pdf_reverse/data/raw/certification/CT/DecertifiedOfficersRev_9622 Emilie Munson.pdf'
    out_path = '/Users/yiminglin/Documents/Codebase/Pdf_reverse/data/truths/key_value_truth/certification/CT/DecertifiedOfficersRev_9622 Emilie Munson_intermediate.txt'

    pdf_2_text_pipeline(in_path, out_path,1)