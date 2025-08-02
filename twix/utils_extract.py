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

