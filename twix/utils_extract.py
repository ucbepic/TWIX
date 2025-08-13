import fitz

def sort_words_by_reading_order(words, y_tolerance=4):
    if not words:
        return words
    
    # group words into lines
    lines = []
    sorted_words = sorted(words, key=lambda w: w['y0'])
    
    current_line = [sorted_words[0]]
    current_y = sorted_words[0]['y0']
    
    for word in sorted_words[1:]:
        if abs(word['y0'] - current_y) <= y_tolerance:
            current_line.append(word)
        else:
            lines.append(current_line)
            current_line = [word]
            current_y = word['y0']
    
    # last line
    if current_line:
        lines.append(current_line)
    
    # sort words in each line by x0
    sorted_result = []
    for line in lines:
        line_sorted = sorted(line, key=lambda w: w['x0'])
        sorted_result.extend(line_sorted)
    
    return sorted_result

def correct_pdf_rotation(src_pdf):
    """
    correct the rotation of all pages in the PDF
    
    Parameters:
        src_pdf: fitz.open() opened PDF document object
    
    Returns:
        corrected PDF document object with all pages rotated to 0 degree
    """
    # create a new output document
    corrected_doc = fitz.open()
    
    for page_num in range(len(src_pdf)):
        src_page = src_pdf[page_num]
        
        # get the size and rotation of the page
        src_rect = src_page.rect
        width, height = src_rect.width, src_rect.height
        src_rotation = src_page.rotation
        
        # if the page has rotation, correct it
        if src_rotation != 0:
            src_page.set_rotation(0)
            new_page = corrected_doc.new_page(width=width, height=height)
            
            new_page.show_pdf_page(
                new_page.rect,
                src_pdf,
                page_num,
                rotate=-src_rotation
            )
            
            src_page.set_rotation(src_rotation)
        else:
            new_page = corrected_doc.new_page(width=width, height=height)
            new_page.show_pdf_page(new_page.rect, src_pdf, page_num)
    
    return corrected_doc