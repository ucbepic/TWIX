import json
import pdfplumber
import os
import math
import time
import fitz
from concurrent.futures import ThreadPoolExecutor, as_completed
import multi_row_process
import traceback

# Configuration options
VERBOSE_LOGGING = True  # Set to False to reduce console output
MAX_WORKERS_MULTIPLIER = 2  # Multiplier for CPU cores when determining max workers

def is_same_row(b1,b2):
    return not (b1[3] < b2[1] or b1[1] > b2[3])

def sort_words_by_reading_order(words, y_tolerance=4):
    if not words:
        return words
    
    pages = {}
    for word in words:
        page_num = word.get('page', 1)
        if page_num not in pages:
            pages[page_num] = []
        pages[page_num].append(word)
    
    sorted_result = []
    for page_num in sorted(pages.keys()):
        page_words = pages[page_num]
        
        # group words into lines
        lines = []
        sorted_words = sorted(page_words, key=lambda w: w['y0'])
        
        if not sorted_words:
            continue
            
        current_line = [sorted_words[0]]
        current_y_avg = sorted_words[0]['y0']
        
        for word in sorted_words[1:]:
            if abs(word['y0'] - current_y_avg) <= y_tolerance:
                current_line.append(word)
                current_y_avg = sum(w['y0'] for w in current_line) / len(current_line)
            else:
                lines.append(current_line)
                current_line = [word]
                current_y_avg = word['y0']
        
        # last line
        if current_line:
            lines.append(current_line)
        
        # sort words in each line by x0
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

def extract_words(path, page_annot=True):
    pdf = fitz.open(path)
    pdf = correct_pdf_rotation(pdf)
        
    words = []
    page_widths = {}  # Store page widths for each page
    
    for page_index in range(len(pdf)):
        if page_index < len(pdf):
            page = pdf[page_index]
            page_rect = page.rect
            page_width = page_rect.width
            page_widths[page_index + 1] = page_width  # Store page width (1-indexed)
            
            page_words = page.get_text("words")
            
            word_dicts = []
            for word_tuple in page_words:
                x0, y0, x1, y1, text, _, _, _ = word_tuple
                
                word_dict = {
                    'text': text,
                    'x0': x0,
                    'y0': y0,
                    'x1': x1,
                    'y1': y1,
                    'top': y0,
                    'bottom': y1,
                    'doctop': y0 + page_index * page.rect.height,
                    'height': y1 - y0,
                    'width': x1 - x0
                }
                
                if page_annot:
                    word_dict['page'] = page_index + 1
                    word_dict['size'] = (x1 - x0) / len(text) if len(text) > 0 else 0
                
                word_dicts.append(word_dict)
            
            
            # handle colon split
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
    
    pdf.close()
    # print(f"Number of words: {len(words)}")
    words = sort_words_by_reading_order(words)
    return words, page_widths

def extract_words_pdfplumber(path, page_indices=list(range(5)), page_annot=True):
    pdf = pdfplumber.open(path)
    words = []
    for page_index in page_indices:
        page = pdf.pages[page_index]
        page_words = page.extract_words(split_at_punctuation=':')
        if page_annot:
            for word in page_words:
                word['page'] = page_index+1
                word['size'] = (word['x1']-word['x0'])/len(word['text'])
                word['y0'] = word['top']
                word['y1'] = word['bottom']
        words.extend(page_words)
    pdf.close()
    return words

def assign_row_to_phrases(phrases):
    # this function will assign each phrase to a row, return a list of rows, each row is a list of phrases
    rows = []
    rows_bbox = []
    phrases_set = set()  # New: collect all unique phrase texts
    used_phrases = set()
    n = len(phrases)
    
    for i in range(n):
        if i in used_phrases:
            continue
            
        phrase = phrases[i]
        # Start a new row with the current phrase
        current_row = [phrase]
        current_row_bbox = [phrase['x0'], phrase['y0'], phrase['x1'], phrase['y1']]
        used_phrases.add(i)
        phrase_bbox = [phrase['x0'], phrase['y0'], phrase['x1'], phrase['y1']]
        phrase_page = phrase['page']
        
        # Find other phrases on the same row
        for j in range(i+1, n):
            if j in used_phrases:
                continue
            other_phrase = phrases[j]
            if other_phrase['page'] != phrase_page:
                continue
            other_bbox = [other_phrase['x0'], other_phrase['y0'], other_phrase['x1'], other_phrase['y1']]
            
            # Check if the phrases are on the same row
            if is_same_row(phrase_bbox, other_bbox):
                current_row.append(other_phrase)
                # update the bbox of the current row
                current_row_bbox[0] = min(current_row_bbox[0], other_bbox[0])
                current_row_bbox[1] = min(current_row_bbox[1], other_bbox[1])
                current_row_bbox[2] = max(current_row_bbox[2], other_bbox[2])
                current_row_bbox[3] = max(current_row_bbox[3], other_bbox[3])
                used_phrases.add(j)
        
        # Sort phrases in the row by x-coordinate (left to right)
        rows.append(current_row)
        rows_bbox.append(current_row_bbox)
    # Extract unique phrase texts from all rows
    for row in rows:
        for phrase in row:
            phrases_set.add(phrase['text'])
    
    # print(rows[0][0])

    return rows, rows_bbox, phrases_set

def is_equal_with_tolerance(value1, value2, tolerance):
    if abs(value1 - value2) <= tolerance:
        return True
    return False

def is_less_than_tolerance(value1, value2, tolerance):
    if value1 < value2 + tolerance:
        return True
    return False

def is_greater_than_tolerance(value1, value2, tolerance):
    if value1 > value2 - tolerance:
        return True
    return False

def is_overlapped_bbox(bbox1, bbox2, x_tolerance=3, y_tolerance=3):
    if bbox1['page'] != bbox2['page']:
        return False
    
    bbox1_x0, bbox1_y0, bbox1_x1, bbox1_y1 = bbox1['x0'], bbox1['y0'], bbox1['x1'], bbox1['y1']
    bbox2_x0, bbox2_y0, bbox2_x1, bbox2_y1 = bbox2['x0'], bbox2['y0'], bbox2['x1'], bbox2['y1']
    
    # Quick check for non-overlapping cases
    if bbox1_x1 + x_tolerance < bbox2_x0 or bbox2_x1 + x_tolerance < bbox1_x0:
        return False
    if bbox1_y1 + y_tolerance < bbox2_y0 or bbox2_y1 + y_tolerance < bbox1_y0:
        return False
    
    # Detailed check with tolerance
    x0_min, x0_max = (bbox1_x0, bbox2_x0) if bbox1_x0 < bbox2_x0 else (bbox2_x0, bbox1_x0)
    x1_min, x1_max = (bbox1_x1, bbox2_x1) if bbox1_x1 < bbox2_x1 else (bbox2_x1, bbox1_x1)
    y0_min, y0_max = (bbox1_y0, bbox2_y0) if bbox1_y0 < bbox2_y0 else (bbox2_y0, bbox1_y0)
    y1_min, y1_max = (bbox1_y1, bbox2_y1) if bbox1_y1 < bbox2_y1 else (bbox2_y1, bbox1_y1)
    
    is_x0_ok = abs(x0_min - x0_max) <= x_tolerance or (x0_min < x0_max and x0_max < x1_min)
    is_x1_ok = abs(x1_min - x1_max) <= x_tolerance or (x1_min < x1_max and x1_min > x0_max)
    is_y0_ok = abs(y0_min - y0_max) <= y_tolerance or (y0_min < y0_max and y0_max < y1_min)
    is_y1_ok = abs(y1_min - y1_max) <= y_tolerance or (y1_min < y1_max and y1_min > y0_max)
    
    return is_x0_ok and is_x1_ok and is_y0_ok and is_y1_ok

def is_vertically_aligned_bbox(bbox1, bbox2, align_tolerance=3):
    bbox1_x0, _, bbox1_x1, _ = bbox1
    bbox2_x0, _, bbox2_x1, _ = bbox2
    if abs(bbox1_x0 - bbox2_x0) > align_tolerance or abs(bbox1_x1 - bbox2_x1) > align_tolerance:
        return False
    return True

def is_horizontally_aligned_bbox(bbox1, bbox2, align_tolerance=3):
    _, bbox1_y0, _, bbox1_y1 = bbox1
    _, bbox2_y0, _, bbox2_y1 = bbox2
    if abs(bbox1_y0 - bbox2_y0) > align_tolerance or abs(bbox1_y1 - bbox2_y1) > align_tolerance:
        return False
    return True

def is_same_bbox(bbox1, bbox2, x_tolerance=0.5, y_tolerance=0.5):
    bbox1_x0, bbox1_y0, bbox1_x1, bbox1_y1 = bbox1
    bbox2_x0, bbox2_y0, bbox2_x1, bbox2_y1 = bbox2
    if abs(bbox1_x0 - bbox2_x0) > x_tolerance or abs(bbox1_y0 - bbox2_y0) > y_tolerance or abs(bbox1_x1 - bbox2_x1) > x_tolerance or abs(bbox1_y1 - bbox2_y1) > y_tolerance:
        return False
    return True

def is_aligned_bbox(bbox1, bbox2, align_tolerance=3):
    return is_vertically_aligned_bbox(bbox1, bbox2, align_tolerance) or is_horizontally_aligned_bbox(bbox1, bbox2, align_tolerance)

def row_compare(row1, row2, matched_texts, row1_bbox, row2_bbox, font_size_tolerance=0.2, non_alphabetical_threshold=3, location_bias_tolerance=1):
    # this function will compare two rows.
    # return True if the two rows are the same
    if len(row1) != len(row2) or row1_bbox is None or row2_bbox is None:
        return False
    len_row = len(row1)

    perfect_match_count = 0
    
    # Track cumulative offsets
    total_x_offset = 0
    total_y_offset = 0
    offset_count = 0

    # Check if the two rows are the same with spatial similarity
    for i, (r1, r2) in enumerate(zip(row1, row2)):
        if r1['text'] != r2['text'] or abs(r1['size'] - r2['size']) > font_size_tolerance:
            return False
        
        # Calculate offsets for this text pair
        x_offset = r2['x0'] - r1['x0']
        y_offset = r2['y0'] - r1['y0']
        
        if offset_count > 0:
            # Calculate average offsets so far
            avg_x_offset = total_x_offset / offset_count
            avg_y_offset = total_y_offset / offset_count
            
            # Check if current offset deviates too much from average
            if abs(x_offset - avg_x_offset) > location_bias_tolerance or abs(y_offset - avg_y_offset) > location_bias_tolerance:
                if VERBOSE_LOGGING:
                    print(f"Row Rejected: {row1[i]['text']} and {row2[i]['text']} due to location bias")
                return False
        
        # Update cumulative offsets
        total_x_offset += x_offset
        total_y_offset += y_offset
        offset_count += 1
        perfect_match_count += 1

    # Some times a value might be missing
    # Count non-alphabetical characters
    non_alphabetical_count = sum(1 for r in row1 if not r['text'].isalpha())
    result = (perfect_match_count == len_row and len_row - non_alphabetical_count > non_alphabetical_threshold)
    if result:
        # Collect texts
        texts = [r['text'] for r in row1]
        if r1['text'] in matched_texts:
            return False
        matched_texts.update(texts)
        print(texts)
    return result


def document_compare(doc1_rows, doc2_rows, doc1_rows_bbox, doc2_rows_bbox, doc1_phrases_set=None, doc2_phrases_set=None, matched_row_threshold=1, doc1_page_widths=None, doc2_page_widths=None, cluster_rep1=None, cluster_rep2=None):
    # this function will compare two documents. compare a row in doc1 with a row in doc2 if they are intersected, return True if there's a match
    matched_row_score = 0
    # Detect local range of rows2 around the current row1
    matched_texts = set()
    for i, row1 in enumerate(doc1_rows):
        for j in range(0, len(doc2_rows)):
            row2 = doc2_rows[j]
            row1_bbox = doc1_rows_bbox[i] if i < len(doc1_rows_bbox) else None
            row2_bbox = doc2_rows_bbox[j] if j < len(doc2_rows_bbox) else None
            result = row_compare(row1, row2, matched_texts, row1_bbox, row2_bbox)
            if result:
                # Check if row length is less than half of page width
                if doc1_page_widths and doc2_page_widths and cluster_rep1 and cluster_rep2:
                    # Calculate row length for both rows
                    row1_page = row1[0]['page'] if row1 else 1
                    row2_page = row2[0]['page'] if row2 else 1
                    
                    # Get row bbox to calculate length
                    row1_bbox = doc1_rows_bbox[i] if i < len(doc1_rows_bbox) else None
                    row2_bbox = doc2_rows_bbox[j] if j < len(doc2_rows_bbox) else None
                    
                    if row1_bbox and row2_bbox:
                        row1_length = row1_bbox[2] - row1_bbox[0]  # x1 - x0
                        row2_length = row2_bbox[2] - row2_bbox[0]  # x1 - x0
                        
                        page1_width = doc1_page_widths.get(row1_page, 0)
                        page2_width = doc2_page_widths.get(row2_page, 0)
                        
                        # Check if both rows are less than half page width
                        if (page1_width > 0 and row1_length < page1_width / 2) or (page2_width > 0 and row2_length < page2_width / 2):
                            if VERBOSE_LOGGING:
                                print("File 1: ", cluster_rep1['file_path'], "File 2: ", cluster_rep2['file_path'])
                            # Use vision similarity check
                            vision_result = check_vision_similarity(cluster_rep1, cluster_rep2)
                            if VERBOSE_LOGGING:
                                print(f"Vision similarity check result: {vision_result}")
                            if vision_result['matched_boxes'] > 0 or vision_result['box_count'] == 0:
                                matched_row_score += result
                            # If vision check fails, don't count this as a match
                        else:
                            # Row is long enough, accept the match
                            matched_row_score += result
                    else:
                        # Can't calculate row length, accept the match
                        matched_row_score += result
                else:
                    # No page width info available, accept the match
                    matched_row_score += result
            
            if matched_row_score >= matched_row_threshold:
                return True
        
    return False

def check_vision_similarity(cluster_rep1, cluster_rep2, vision_merge_threshold=10):
    """
    Check vision similarity between two cluster representatives using rectangle extraction.
    
    Args:
        cluster_rep1: First cluster representative
        cluster_rep2: Second cluster representative  
        vision_merge_threshold: Threshold for minimum vertically aligned boxes
        
    Returns:
        tuple: (is_similar, aligned_boxes_count, vertically_aligned_boxes)
    """
    try:
        doc1 = fitz.open(cluster_rep1['pdf_path'])
        page1 = doc1[0]
        hlines1, vlines1 = multi_row_process.extract_lines_from_pdf_page(page1)
        doc2 = fitz.open(cluster_rep2['pdf_path'])
        page2 = doc2[0]
        hlines2, vlines2 = multi_row_process.extract_lines_from_pdf_page(page2)
        pipeline = multi_row_process.MultiRowProcessPipeline()
        words1 = [w for row in cluster_rep1['rows'] for w in row if w['page'] == 1]
        words2 = [w for row in cluster_rep2['rows'] for w in row if w['page'] == 1]
        
        # Extract all boxes
        rects1 = pipeline.find_rectangles(hlines1, vlines1)
        rects2 = pipeline.find_rectangles(hlines2, vlines2)
        if len(rects1) == 0 or len(rects2) == 0:
            return {"is_similar": False, "matched_boxes": 0, "box_count": 0}
            
        boxes1 = [(rect[0][0], rect[0][1], rect[1][0], rect[1][1]) for rect in rects1]
        boxes2 = [(rect[0][0], rect[0][1], rect[1][0], rect[1][1]) for rect in rects2]
        
        # Extract all words in the boxes
        grouping_result1 = pipeline.group_text_by_boxes(words1, boxes1)
        grouping_result2 = pipeline.group_text_by_boxes(words2, boxes2)
        
        # Find all the boxes that vertically aligned and has the same beginning text
        text_boxes1 = grouping_result1['grouped']
        text_boxes2 = grouping_result2['grouped']
        vertically_aligned_boxes = []
        
        for box1, words1 in text_boxes1.items():
            x0_1, y0_1, x1_1, y1_1 = box1
            
            if words1:
                first_word1 = words1[0]['text'] if words1 else ""
                # skip if the first word's first letter is not uppercase or the box is too small
                if not first_word1[0].isupper() or x1_1 - x0_1 < 10:
                    continue
                for box2, words2 in text_boxes2.items():
                    x0_2, y0_2, x1_2, y1_2 = box2
                    
                    bbox1 = [x0_1, y0_1, x1_1, y1_1]
                    bbox2 = [x0_2, y0_2, x1_2, y1_2]
                    if is_vertically_aligned_bbox(bbox1, bbox2, align_tolerance=5):
                        if words2:
                            first_word2 = words2[0]['text'] if words2 else ""
                            if first_word1 == first_word2 and first_word1 and is_same_bbox(box1, box2):
                                vertically_aligned_boxes.append((box1, box2, first_word1))
        
        doc1.close()
        doc2.close()
        
        is_similar = len(vertically_aligned_boxes) > vision_merge_threshold
        return {"is_similar": is_similar, "matched_boxes": len(vertically_aligned_boxes), "box_count": min(len(boxes1), len(boxes2))}
        
    except Exception as e:
        if VERBOSE_LOGGING:
            print(f"Error in vision similarity check: {e}")
        return {"is_similar": False, "matched_boxes": 0, "box_count": 0}

def get_rows_from_pdf(pdf_path):
    words, page_widths = extract_words(pdf_path)
    # phrases = get_phrases_dynamic(words) # lead to wrong result in documents with too much kv pairs
    rows, rows_bbox, phrases_set = assign_row_to_phrases(words)
    return rows, rows_bbox, phrases_set, page_widths

def get_rows_from_pdf_with_count(pdf_path):
    """Helper function for parallel processing that returns rows with phrase count"""
    rows, rows_bbox, phrases_set, page_widths = get_rows_from_pdf(pdf_path)
    phrase_count = sum(len(row) for row in rows)
    return pdf_path, rows, rows_bbox, phrases_set, phrase_count, page_widths

def parallel_pdf_extraction(files, max_workers=None):
    """Extract PDF rows in parallel using ThreadPoolExecutor"""
    if max_workers is None:
        max_workers = min(len(files), os.cpu_count() * MAX_WORKERS_MULTIPLIER)
    
    pdf_data = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {executor.submit(get_rows_from_pdf_with_count, file): file 
                         for file in files}
        
        for future in as_completed(future_to_file):
            try:
                file_path, rows, rows_bbox, phrases_set, phrase_count, page_widths = future.result()
                pdf_data[file_path] = (rows, rows_bbox, phrases_set, phrase_count, file_path, page_widths)
            except Exception as e:
                print(f"Error processing {future_to_file[future]}: {e}")
    
    return pdf_data


def document_cluster(files, final_sort=False, vision_merge_threshold=10):
    """
    Cluster documents using initial assignment followed by iterative merging.
    Each document starts in its own cluster, then clusters are merged iteratively
    until no more changes occur.
    
    PDF extraction is done in parallel, but cluster merging is single-threaded.
    """
    
    if VERBOSE_LOGGING:
        print("Step 1: Extracting PDF data in parallel...")
    # Step 1: Parallel PDF extraction - each document gets its own cluster initially
    pdf_data = parallel_pdf_extraction(files)
    
    # Step 2: Initial cluster assignment - each document starts in its own cluster
    if VERBOSE_LOGGING:
        print("Step 2: Initial cluster assignment...")
    clusters = []
    for file in files:
        if file in pdf_data:
            rows, rows_bbox, phrases_set, phrase_count, pdf_path, page_widths = pdf_data[file]
            
            # Create a new cluster for each document initially
            clusters.append([{
                "file_path": file, 
                "rows": rows, 
                "rows_bbox": rows_bbox, 
                "phrases_set": phrases_set, 
                "phrase_count": phrase_count,
                "pdf_path": pdf_path,
                "page_widths": page_widths
            }])
    
    if VERBOSE_LOGGING:
        print(f"Initial clusters created: {len(clusters)}")
    
    # Step 3: Iterative merging until no changes occur
    if VERBOSE_LOGGING:
        print("Step 3: Starting iterative cluster merging...")
    round_num = 0
    total_merges = 0
    
    while True:
        round_num += 1
        if VERBOSE_LOGGING:
            print(f"\n--- Starting merge round {round_num} ---")
        
        # Track if any changes occurred in this round
        changes_made = False
        clusters_to_remove = set()
        merges_this_round = 0
        
        # Single-threaded cluster comparison and merging
        for i in range(len(clusters)):
            if i in clusters_to_remove:
                continue
                
            for j in range(i + 1, len(clusters)):
                if j in clusters_to_remove:
                    continue
                
                # Get representatives from both clusters (use the document with most phrases as representative)
                cluster_i_rep = max(clusters[i], key=lambda x: x['phrase_count'])
                cluster_j_rep = max(clusters[j], key=lambda x: x['phrase_count'])
                
                # Check if clusters can be merged
                if document_compare(
                    cluster_i_rep['rows'], cluster_j_rep['rows'],
                    cluster_i_rep['rows_bbox'], cluster_j_rep['rows_bbox'],
                    cluster_i_rep['phrases_set'], cluster_j_rep['phrases_set'],
                    matched_row_threshold=1,
                    doc1_page_widths=cluster_i_rep.get('page_widths'),
                    doc2_page_widths=cluster_j_rep.get('page_widths'),
                    cluster_rep1=cluster_i_rep,
                    cluster_rep2=cluster_j_rep
                ):
                    # Merge cluster_j into cluster_i
                    clusters[i].extend(clusters[j])
                    clusters_to_remove.add(j)
                    changes_made = True
                    merges_this_round += 1
                    if VERBOSE_LOGGING:
                        print(f"  ✓ Merged cluster {j} into cluster {i}")
                        print(f"    This is a match between {cluster_i_rep['file_path']} and {cluster_j_rep['file_path']}")
                        print(f"    Cluster {i} now contains {len(clusters[i])} documents")
                elif cluster_i_rep['phrases_set'] is not None and cluster_j_rep['phrases_set'] is not None:
                    intersection = cluster_i_rep['phrases_set'].intersection(cluster_j_rep['phrases_set'])
                    # Filter out intersection words that have no more than 3 characters
                    intersection = [word for word in intersection if len(word) >= 3]
                    # Filter out intersection words whose half of characters are digits
                    intersection = [word for word in intersection if sum(c.isdigit() for c in word) <= len(word) / 2]
                    # print(intersection)
                    if len(intersection) > 50:
                        # Extract all boxes from cluster_i_rep and cluster_j_rep using multirow_process
                        doc1 = fitz.open(cluster_i_rep['pdf_path'])
                        page1 = doc1[0]
                        hlines1, vlines1  = multi_row_process.extract_lines_from_pdf_page(page1)
                        doc2 = fitz.open(cluster_j_rep['pdf_path'])
                        page2 = doc2[0]
                        hlines2, vlines2  = multi_row_process.extract_lines_from_pdf_page(page2)
                        pipeline = multi_row_process.MultiRowProcessPipeline()
                        words1 = [w for row in cluster_i_rep['rows'] for w in row if w['page'] == 1]
                        words2 = [w for row in cluster_j_rep['rows'] for w in row if w['page'] == 1]
                        # Extract all boxes
                        rects1 = pipeline.find_rectangles(hlines1, vlines1)
                        rects2 = pipeline.find_rectangles(hlines2, vlines2)
                        if len(rects1) == 0 or len(rects2) == 0:
                            continue
                        boxes1 = [(rect[0][0], rect[0][1], rect[1][0], rect[1][1]) for rect in rects1]
                        boxes2 = [(rect[0][0], rect[0][1], rect[1][0], rect[1][1]) for rect in rects2]
                        # Extract all words in the boxes
                        grouping_result1 = pipeline.group_text_by_boxes(words1, boxes1)
                        grouping_result2 = pipeline.group_text_by_boxes(words2, boxes2)
                        # Step 1. Find all the boxes that vertically aligned and has the same beginning text
                        # Note that in grouping_result1/2, a containning box might contains multiple words, and we need concat them
                        text_boxes1 = grouping_result1['grouped']
                        text_boxes2 = grouping_result2['grouped']
                        vertically_aligned_boxes = []
                        
                        for box1, words1 in text_boxes1.items():
                            x0_1, y0_1, x1_1, y1_1 = box1
                            
                            if words1:
                                first_word1 = words1[0]['text'] if words1 else ""
                                # skip if the first word's first letter is not uppercase or the box is too small
                                if not first_word1[0].isupper() or x1_1 - x0_1 < 10:
                                    continue
                                for box2, words2 in text_boxes2.items():
                                    x0_2, y0_2, x1_2, y1_2 = box2
                                    
                                    bbox1 = [x0_1, y0_1, x1_1, y1_1]
                                    bbox2 = [x0_2, y0_2, x1_2, y1_2]
                                    if is_vertically_aligned_bbox(bbox1, bbox2, align_tolerance=5):
                                        if words2:
                                            first_word2 = words2[0]['text'] if words2 else ""
                                            if first_word1 == first_word2 and first_word1 and is_same_bbox(box1, box2):
                                                vertically_aligned_boxes.append((box1, box2, first_word1))
                        
                        # Step 2. Merge cluster_j into cluster_i if the number of vertically aligned boxes is greater than vision_merge_threshold or the ratio of vertically aligned boxes to the total number of boxes is greater than 80%
                        if len(vertically_aligned_boxes) > vision_merge_threshold:
                            if VERBOSE_LOGGING:
                                print(f"  ✓ Found {len(vertically_aligned_boxes)} vertically aligned boxes with same beginning text")
                                print(f"    Sample aligned boxes: {[text for _, _, text in vertically_aligned_boxes[:3]]}")
                            
                            clusters[i].extend(clusters[j])
                            clusters_to_remove.add(j)
                            changes_made = True
                            merges_this_round += 1
                            if VERBOSE_LOGGING:
                                print(f"  ✓ Merged cluster {j} into cluster {i} based on vertically aligned boxes")
                                print(f"    Cluster {i} now contains {len(clusters[i])} documents")
                        else:
                            if VERBOSE_LOGGING:
                                print(f"  ✗ Clusters {i} and {j} have {len(vertically_aligned_boxes)} vertically aligned boxes, below threshold of {vision_merge_threshold}")


        # Remove merged clusters (in reverse order to maintain indices)
        for idx in sorted(clusters_to_remove, reverse=True):
            del clusters[idx]
        
        total_merges += merges_this_round
        if VERBOSE_LOGGING:
            print(f"Round {round_num} completed:")
            print(f"  - Merges this round: {merges_this_round}")
            print(f"  - Total merges so far: {total_merges}")
            print(f"  - Remaining clusters: {len(clusters)}")
            print(f"  - Changes made: {changes_made}")
        
        # DEBUG
        # changes_made = False
        # If no changes were made, we're done
        if not changes_made:
            if VERBOSE_LOGGING:
                print(f"\n🎯 No more changes after round {round_num}. Clustering complete!")
                print(f"Final cluster count: {len(clusters)}")
            break
    
    # Final sorting if requested
    if final_sort:
        if VERBOSE_LOGGING:
            print("Applying final sorting to clusters...")
        for cluster in clusters:
            cluster.sort(key=lambda x: x['file_path'])
    
    return clusters

if __name__ == "__main__":
    # file_num = #files in the cluster_data
    data_folder = 'path/to/tests/cluster_data/'
    os.chdir(data_folder)
    
    # Get all PDF files in the data folder
    pdf_files = [f for f in os.listdir(data_folder) if f.endswith('.pdf')]
    file_num = len(pdf_files)
    
    if file_num == 0:
        print("❌ No PDF files found in the data folder!")
        exit(1)
    
    print(f"Data folder: {data_folder}")
    print(f"Number of PDF files found: {file_num}")
    print(f"CPU cores available: {os.cpu_count()}")
    print("=" * 50)
    
    # Build full file paths
    files = [os.path.join(data_folder, f) for f in pdf_files]
    
    # Run clustering
    print("🚀 Starting document clustering process...")
    t1 = time.time()
    
    try:
        clusters = document_cluster(files, True)
        t2 = time.time()
        
        # Display results
        print("\n" + "=" * 50)
        print("📊 CLUSTERING RESULTS")
        print("=" * 50)
        
        total_docs = sum(len(cluster) for cluster in clusters)
        print(f"Total documents processed: {total_docs}")
        print(f"Final cluster count: {len(clusters)}")
        print(f"Time taken: {t2 - t1:.2f} seconds")
        # print(f"Average time per document: {(t2 - t1) / total_docs:.3f} seconds")
        
        # Display each cluster with progress bar
        print(f"\n📋 Cluster Details:")
        for i, cluster in enumerate(clusters):
            print(f"\n🔸 Cluster {i + 1} ({len(cluster)} documents):")
            for j, file_info in enumerate(cluster):
                file_name = os.path.basename(file_info['file_path'])
                phrase_count = file_info['phrase_count']
                print(f"  {j + 1:2d}. {file_name} ({phrase_count} phrases)")
        
        # Performance metrics
        docs_per_second = total_docs / (t2 - t1)
        print(f"  - Processing speed: {docs_per_second:.1f} docs/second")
        
        # Validate the clusters
        # 1. Collect the file_path of each cluster and remove the heading 9 characters, and the suffix that begins with '-'
        # 2. Check if every file_path in the cluster is the same and unique
        existing_file_paths = set()
        
        print(f"\n🔍 CLUSTER VALIDATION")
        print("=" * 50)
        
        validation_errors = []
        cluster_validation_results = []
        
        for i, cluster in enumerate(clusters):
            print(f"\n🔸 Validating Cluster {i + 1} ({len(cluster)} documents):")
            
            # Extract and normalize file paths for this cluster
            cluster_file_paths = []
            for file_info in cluster:
                file_path = file_info['file_path']
                file_name = os.path.basename(file_path)
                
                # Remove heading 9 characters and suffix that begins with '-'
                if len(file_name) > 9:
                    # Remove first 9 characters
                    name_without_prefix = file_name[9:]
                    
                    # Remove suffix that begins with '-'
                    if '-' in name_without_prefix:
                        name_without_prefix = name_without_prefix.split('-')[0]
                    
                    cluster_file_paths.append(name_without_prefix)
                else:
                    cluster_file_paths.append(file_name)
            
            # Check if all file paths in the cluster are the same
            unique_paths = set(cluster_file_paths)
            if len(unique_paths) == 1:
                # All files in cluster have the same normalized path
                normalized_path = list(unique_paths)[0]
                print(f"  ✅ All files have same normalized path: {normalized_path}")
                status = 'valid'
                # Check if this path is unique across all clusters
                if normalized_path in existing_file_paths:
                    validation_errors.append(f"Cluster {i + 1}: Duplicate normalized path '{normalized_path}' found in multiple clusters")
                    print(f"  ❌ ERROR: Duplicate normalized path '{normalized_path}' found in multiple clusters")
                    status = 'duplicate_path'
                else:
                    existing_file_paths.add(normalized_path)
                    print(f"  ✅ Normalized path '{normalized_path}' is unique")
                cluster_validation_results.append({
                    'cluster_id': i + 1,
                    'status': status,
                    'normalized_path': normalized_path,
                    'file_count': len(cluster),
                    'original_files': [os.path.basename(f['file_path']) for f in cluster]
                })
            else:
                # Files in cluster have different normalized paths
                error_msg = f"Cluster {i + 1}: Files have different normalized paths: {unique_paths}"
                validation_errors.append(error_msg)
                print(f"  ❌ ERROR: {error_msg}")
                
                cluster_validation_results.append({
                    'cluster_id': i + 1,
                    'status': 'mixed_paths',
                    'normalized_paths': list(unique_paths),
                    'file_count': len(cluster),
                    'original_files': [os.path.basename(f['file_path']) for f in cluster]
                })
        
        # Summary of validation results
        print(f"\n📊 VALIDATION SUMMARY")
        print("=" * 50)
        
        valid_clusters = sum(1 for result in cluster_validation_results if result['status'] == 'valid')
        duplicate_path_clusters = sum(1 for result in cluster_validation_results if result['status'] == 'duplicate_path')
        mixed_paths_clusters = sum(1 for result in cluster_validation_results if result['status'] == 'mixed_paths')
        
        print(f"Total docs: {total_docs}")
        print(f"Total clusters: {len(clusters)}")
        print(f"✅ Valid clusters: {valid_clusters}")
        print(f"⚠️  Clusters with duplicate docs: {duplicate_path_clusters}")
        print(f"❌ Clusters with mixed docs: {mixed_paths_clusters}")
        print(f"Processing time: {t2 - t1:.2f} seconds")

        if validation_errors:
            print(f"\n❌ VALIDATION ERRORS FOUND:")
            for error in validation_errors:
                print(f"  - {error}")
        else:
            print(f"\n🎉 All clusters passed validation!")

    except Exception as e:
        print(f"\n❌ Error during clustering: {e}")
        traceback.print_exc()
        exit(1)
