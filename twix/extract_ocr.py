import os
import fitz
import numpy as np
import io
from PIL import Image
from . import utils_extract

def _pdfpage2npimage(page, zoom):
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    img_data = pix.tobytes("png")
    img = Image.open(io.BytesIO(img_data))
    img_np = np.array(img)
    return img_np

def _process_word_tuple(text, bbox, confidence, page_index, zoom_factor, page_annot=True):
    # Convert image coordinates to PDF coordinates
    scale = 1.0 / zoom_factor
    # if the shape of bbox is (4, 2)
    if len(bbox) == 4 and (isinstance(bbox[0], np.ndarray) or isinstance(bbox[0], list)): 
        x_coords = [point[0] * scale for point in bbox]
        y_coords = [point[1] * scale for point in bbox]
        
        x0 = min(x_coords)
        y0 = min(y_coords)
        x1 = max(x_coords)
        y1 = max(y_coords)
    elif len(bbox) == 4:
        x0, y0, x1, y1 = bbox
        x0 *= scale
        y0 *= scale
        x1 *= scale
        y1 *= scale
    else:
        raise ValueError(f"Invalid bbox format: {bbox}")

    word_dict = {
        'text': text,
        'x0': x0,
        'y0': y0,
        'x1': x1,
        'y1': y1,
        'top': y0,
        'bottom': y1,
        'height': y1 - y0,
        'width': x1 - x0
    }
    
    if page_annot:
        word_dict['page'] = page_index + 1
        word_dict['size'] = (x1 - x0) / len(text) if len(text) > 0 else 0

    return word_dict


def _process_word_dicts(word_dicts, page_index, page_annot=True):
    """
    Shared helper function to process word dictionaries after OCR extraction.
    Handles sorting by reading order and colon splitting.
    """
    words = []
    
    # Sort words by reading order
    word_dicts = utils_extract.sort_words_by_reading_order(word_dicts)
    
    # Handle colon splitting (same logic as PyMuPDF version)
    for word_dict in word_dicts:
        text = word_dict['text']
        if ':' in text:
            parts = text.split(':')
            x0, x1 = word_dict['x0'], word_dict['x1']
            current_x = x0
            
            for i, part in enumerate(parts):
                if part:  # ignore empty string
                    part_width = (x1 - x0) * len(part) / len(text)
                    part_dict = word_dict.copy()
                    part_dict['text'] = part
                    part_dict['x0'] = current_x
                    part_dict['x1'] = current_x + part_width
                    part_dict['width'] = part_width
                    if page_annot:
                        part_dict['size'] = part_width / len(part) if len(part) > 0 else 0
                        part_dict['page'] = page_index + 1
                    words.append(part_dict)
                    current_x += part_width
                
                if i < len(parts) - 1:  # add colon as a separate word
                    colon_width = (x1 - x0) / len(text)
                    colon_dict = word_dict.copy()
                    colon_dict['text'] = ':'
                    colon_dict['x0'] = current_x
                    colon_dict['x1'] = current_x + colon_width
                    colon_dict['width'] = colon_width
                    if page_annot:
                        colon_dict['size'] = colon_width
                        colon_dict['page'] = page_index + 1
                    words.append(colon_dict)
                    current_x += colon_width
        else:
            words.append(word_dict)
    
    return words

def _vertical_lines_word_split(word_dicts, image, zoom_factor, page_annot=True, ):
    import cv2
    
    if not word_dicts:
        return word_dicts
    
    # Detect vertical lines
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(~gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                    cv2.THRESH_BINARY, 15, -2)
    
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
    detected_vertical_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel, iterations=2)
    contours_v, _ = cv2.findContours(detected_vertical_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Extract vertical line coordinates
    vertical_lines = []
    for contour in contours_v:
        x, y, w, h = cv2.boundingRect(contour)
        if h > 20:  # Filter out short lines
            # Store line as (x_position, y_start, y_end)
            x_real = (x + w//2) / zoom_factor
            y0 = y / zoom_factor
            y1 = (y + h) / zoom_factor
            vertical_lines.append((x_real, y0, y1))
    
    if not vertical_lines:
        return word_dicts
    
    # Sort vertical lines by x-coordinate for efficient processing
    vertical_lines.sort(key=lambda line: line[0])
    
    # Process words and split those intersected by vertical lines
    result_words = []
    
    for word_dict in word_dicts:
        word_x0, word_y0, word_x1, word_y1 = word_dict['x0'], word_dict['y0'], word_dict['x1'], word_dict['y1']
        text = word_dict['text']
        
        # Find vertical lines that intersect this word
        intersecting_lines = []
        for line_x, line_y0, line_y1 in vertical_lines:
            # Check if line intersects word horizontally and vertically
            if (word_x0 <= line_x <= word_x1 and 
                not (line_y1 < word_y0 or line_y0 > word_y1)):
                intersecting_lines.append(line_x)
        
        if not intersecting_lines:
            # No intersection, keep original word
            result_words.append(word_dict)
        else:
            # Sort intersecting lines by x-coordinate
            intersecting_lines.sort()
            
            # Split word at each intersecting line
            split_words = _split_word_at_lines(word_dict, intersecting_lines, page_annot)
            result_words.extend(split_words)
    
    return result_words


def _split_word_at_lines(word_dict, line_x_positions, page_annot=True):
    """
    Split a word at multiple vertical line positions.
    
    Args:
        word_dict: Original word dictionary
        line_x_positions: List of x-coordinates where to split (sorted)
        page_annot: Boolean flag for page annotations
        
    Returns:
        List of split word dictionaries
    """
    text = word_dict['text']
    word_x0, word_x1 = word_dict['x0'], word_dict['x1']
    word_width = word_x1 - word_x0
    
    if not text or word_width <= 0:
        return [word_dict]
    
    # Calculate character positions for splitting
    char_width = word_width / len(text)
    split_positions = []
    
    for line_x in line_x_positions:
        # Find the character position closest to the line
        relative_x = line_x - word_x0
        char_pos = int(round(relative_x / char_width))
        # Ensure split position is within text bounds
        char_pos = max(1, min(char_pos, len(text) - 1))
        if char_pos not in split_positions:
            split_positions.append(char_pos)
    
    if not split_positions:
        return [word_dict]
    
    # Sort split positions
    split_positions.sort()
    
    # Create split words
    split_words = []
    start_pos = 0
    start_x = word_x0
    
    for split_pos in split_positions + [len(text)]:
        if start_pos < split_pos:
            # Create word part
            part_text = text[start_pos:split_pos]
            part_width = len(part_text) * char_width
            part_x1 = start_x + part_width
            
            # Create new word dictionary
            part_dict = word_dict.copy()
            part_dict['text'] = part_text
            part_dict['x0'] = start_x
            part_dict['x1'] = part_x1
            part_dict['width'] = part_width
            
            if page_annot and 'size' in word_dict:
                part_dict['size'] = part_width / len(part_text) if len(part_text) > 0 else 0
            
            split_words.append(part_dict)
            
            # Update for next iteration
            start_pos = split_pos
            start_x = part_x1
    
    return split_words

def extract_words_tesseract(path, zoom_factor, page_indices=list(range(5)), page_annot=True):
    try:
        import pytesseract
    except ImportError:
        raise ImportError("Tesseract OCR not found. Please install pytesseract and ensure tesseract is in your PATH")
    
    doc = fitz.open(path)
    words = []
    
    for page_index in page_indices:
        if page_index >= len(doc):
            continue
            
        page = doc[page_index]
        
        # Convert page to image for Tesseract
        img_np = _pdfpage2npimage(page, zoom_factor)
        
        # Use Tesseract to extract text with bounding boxes
        ocr_data = pytesseract.image_to_data(img_np, output_type=pytesseract.Output.DICT)
        
        word_dicts = []
        
        # Process Tesseract results
        for i in range(len(ocr_data['text'])):
            text = ocr_data['text'][i].strip()
            confidence = ocr_data['conf'][i]
            
            # Filter out empty text and low confidence results
            if text and confidence > 0:
                bbox = [ocr_data['left'][i], ocr_data['top'][i], ocr_data['left'][i] + ocr_data['width'][i], ocr_data['top'][i] + ocr_data['height'][i]]
                
                word_dict = _process_word_tuple(text, bbox, confidence, page_index, zoom_factor, page_annot)
                word_dicts.append(word_dict)
        
        # Process word dictionaries using shared helper
        page_words = _process_word_dicts(word_dicts, page_index, page_annot)
        page_words = _vertical_lines_word_split(page_words, img_np, page_annot)
        words.extend(page_words)
    
    doc.close()
    return words

def extract_words_easyocr(path, zoom_factor, page_indices=list(range(5)), page_annot=True):
    try:
       import easyocr
    except ImportError:
        raise ImportError("EasyOCR not found. Please install easyocr")
    reader = easyocr.Reader(['en'], gpu=True)
    
    doc = fitz.open(path)
    words = []
    for page_index in page_indices:
        if page_index >= len(doc):
            continue
            
        page = doc[page_index]
        
        img_np = _pdfpage2npimage(page, zoom_factor)
        results = reader.readtext(img_np)
        
        word_dicts = []
        
        for bbox, text, confidence in results:               
            word_dict = _process_word_tuple(text, bbox, confidence, page_index, zoom_factor, page_annot)
            word_dicts.append(word_dict)
        
        page_words = _process_word_dicts(word_dicts, page_index, page_annot)
        page_words = _vertical_lines_word_split(page_words, img_np, page_annot)
        words.extend(page_words)
    
    doc.close()
    return words


def extract_words_rapidocr(path, zoom_factor, page_indices=list(range(5)), page_annot=True):
    try:
        from rapidocr import RapidOCR
    except ImportError:
        raise ImportError("RapidOCR not found. Please install rapidocr")

    ocr = RapidOCR()
    doc = fitz.open(path)
    words = []
    
    for page_index in page_indices:
        if page_index >= len(doc):
            continue
            
        page = doc[page_index]
        img_np = _pdfpage2npimage(page, zoom_factor)
        
        results = ocr(img_np)

        word_dicts = []
        
        for i, text in enumerate(results.txts):
            bbox = results.boxes[i]
            confidence = results.scores[i]

            word_dict = _process_word_tuple(text, bbox, confidence, page_index, zoom_factor, page_annot)
            word_dicts.append(word_dict)
        
        page_words = _process_word_dicts(word_dicts, page_index, page_annot)
        page_words = _vertical_lines_word_split(page_words, img_np, zoom_factor, page_annot)
        words.extend(page_words)
    
    doc.close()
    return words

def extract_words_paddleocr(path, zoom_factor, page_indices=list(range(5)), page_annot=True):
    try:
        from paddleocr import PaddleOCR
    except ImportError:
        raise ImportError("PaddleOCR not found. Please install paddlepaddle and paddleocr")
    import cv2
    ocr = PaddleOCR(use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=True, lang='en')
    doc = fitz.open(path)
    words = []
    for page_index in page_indices:
        if page_index >= len(doc):
            continue
            
        page = doc[page_index]
        img_np = _pdfpage2npimage(page, zoom_factor)
        image = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        
        results = ocr.predict(image)
        results = results[0]
        
        word_dicts = []
        
        for i, text in enumerate(results["rec_texts"]):
            bbox = [val.astype(float) for val in results["rec_boxes"][i]]
            confidence = results["rec_scores"][i]
                                           
            word_dict = _process_word_tuple(text, bbox, confidence, page_index, zoom_factor, page_annot)
            word_dicts.append(word_dict)
        
        page_words = _process_word_dicts(word_dicts, page_index, page_annot)
        page_words = _vertical_lines_word_split(page_words, image, zoom_factor, page_annot)
        words.extend(page_words)
    
    doc.close()
    return words

def extract_words_ocr(path, page_indices=list(range(5)), page_annot=True, ocr_method = 'tesseract'):
    if ocr_method == 'easyocr':
        return extract_words_easyocr(path, 4.0, page_indices, page_annot)
    elif ocr_method == 'tesseract':
        return extract_words_tesseract(path, 2.0, page_indices, page_annot)
    elif ocr_method == 'rapidocr':
        return extract_words_rapidocr(path, 2.0, page_indices, page_annot)
    elif ocr_method == 'paddleocr':
        return extract_words_paddleocr(path, 2.0, page_indices, page_annot)
    else:
        raise ValueError(f"Invalid ocr_method: {ocr_method}")