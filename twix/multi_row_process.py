import numpy as np
from typing import List, Tuple, Set, Dict, Optional
from collections import defaultdict
import math
import os
from openai import OpenAI
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from functools import partial
import fitz
from . import utils_extract

def extract_lines_from_pdf_page(page, tolerance = 5.0):
    vlines = []
    hlines = []

    drawings = page.get_drawings()
    for drawing in drawings:
        for item in drawing["items"]:
            if item[0] == "l":  # Line
                p1, p2 = item[1], item[2]
                if abs(p1[0] - p2[0]) < tolerance:  # Vertical line
                    vlines.append(('v', min(p1[1], p2[1]), max(p1[1], p2[1]), p1[0]))
                elif abs(p1[1] - p2[1]) < tolerance:  # Horizontal line
                    hlines.append(('h', min(p1[0], p2[0]), max(p1[0], p2[0]), p1[1]))
            elif item[0] == "re":  # Rectangle
                rect = item[1]
                if rect.width < tolerance:  # Vertical line
                    vlines.append(('v', rect.y0, rect.y1, rect.x0))
                elif rect.height < tolerance:  # Horizontal line
                    hlines.append(('h', rect.x0, rect.x1, rect.y0))
                else:  # Full rectangle
                    # print("Rectangle height": rect.height)
                    hlines.extend([
                        ('h', rect.x0, rect.x1, rect.y0),  # Top
                        ('h', rect.x0, rect.x1, rect.y1),  # Bottom
                    ])
                    vlines.extend([
                        ('v', rect.y0, rect.y1, rect.x0),  # Left
                        ('v', rect.y0, rect.y1, rect.x1)   # Right
                    ])

    return hlines, vlines

class MultiRowProcessPipeline:
    
    def __init__(self, 
                 # Box detect
                 tolerance=1e-9, 
                 merge_tolerance=3, 
                 intersection_tolerance=1, 
                 min_box_size=3, 
                 naked_point_tolerance=1,
                 # Text group
                 y_tolerance=5.0, 
                 x_tolerance=10.0, 
                 text_margin=5.0,
                 # Semantic analysis
                 model_name='gpt-4o',
                 batch_size=10,
                 # Multithreading
                 max_workers=None,
                 enable_multithreading=True):
        # Box detect
        self.tolerance = tolerance
        self.merge_tolerance = merge_tolerance
        self.intersection_tolerance = intersection_tolerance
        self.min_box_size = min_box_size
        self.naked_point_tolerance = intersection_tolerance
        
        # Text group
        self.y_tolerance = y_tolerance
        self.x_tolerance = x_tolerance
        self.text_margin = text_margin
        
        # Semantic analysis
        self.model_name = model_name
        self.batch_size = batch_size
        
        # Multithreading
        self.max_workers = max_workers if max_workers is not None else min(32, (os.cpu_count() or 1) + 4)
        self.enable_multithreading = enable_multithreading
        self._lock = threading.Lock()
        
        # Initialize OpenAI client if API key is provided
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            self.client = OpenAI(api_key=api_key)
        else:
            self.client = None
            print("Warning: No OpenAI API key provided. Semantic analysis will be limited.")
        
        # Performance monitoring
        self.performance_stats = {
            'box_detection_time': 0,
            'text_grouping_time': 0,
            'text_aggregation_time': 0,
            'semantic_analysis_time': 0,
            'total_time': 0
        }
    
    def set_multithreading(self, enabled: bool = True):
        # Enable or disable multithreading
        self.enable_multithreading = enabled
        
    def set_max_workers(self, max_workers: int):
        # Set maximum number of worker threads
        self.max_workers = max_workers
    
    def get_performance_stats(self) -> Dict:
        # Get performance statistics
        return self.performance_stats.copy()
    
    # ========== Box Detection Methods ==========
    
    def _get_tolerance_key(self, value: float) -> str:
        rounded = math.ceil(value / self.merge_tolerance) * self.merge_tolerance
        return f"{rounded:.1f}"
    
    def find_rectangles(self, horizontal_segments: List[Tuple], 
                       vertical_segments: List[Tuple]) -> List[Tuple]:
        # Find all rectangles in the page
        h_merged = self._merge_horizontal_segments(horizontal_segments)
        v_merged = self._merge_vertical_segments(vertical_segments)
        
        intersections = self._find_all_intersections(h_merged, v_merged)
        
        rectangles = self._detect_rectangles(intersections, h_merged, v_merged)
        
        return rectangles
    
    def _merge_horizontal_segments(self, segments: List[Tuple]) -> List[Tuple]:
        current_segments = segments.copy()
        max_iterations = 10
        
        for iteration in range(max_iterations):
            groups = defaultdict(list)
            y_values = defaultdict(list)
            bias = self.merge_tolerance * (max_iterations - iteration) / max_iterations
            
            for seg in current_segments:
                _, x0, x1, y = seg
                biased_y = y + bias
                key = self._get_tolerance_key(biased_y)
                groups[key].append((min(x0, x1), max(x0, x1)))
                y_values[key].append(y)
            
            merged = []
            for key, intervals in groups.items():
                avg_y = sum(y_values[key]) / len(y_values[key])
                merged_intervals = self._merge_intervals(intervals)
                for x0, x1 in merged_intervals:
                    merged.append(("h", x0, x1, avg_y))
            
            if len(merged) == len(current_segments):
                break
            
            current_segments = merged
        
        current_segments.sort(key=lambda seg: seg[3])
        return current_segments
    
    def _merge_vertical_segments(self, segments: List[Tuple]) -> List[Tuple]:
        current_segments = segments.copy()
        max_iterations = 10
        
        for iteration in range(max_iterations):
            groups = defaultdict(list)
            x_values = defaultdict(list)
            bias = self.merge_tolerance * (max_iterations - iteration) / max_iterations
            
            for seg in current_segments:
                _, y0, y1, x = seg
                biased_x = x + bias
                key = self._get_tolerance_key(biased_x)
                groups[key].append((min(y0, y1), max(y0, y1)))
                x_values[key].append(x)
            
            merged = []
            for key, intervals in groups.items():
                avg_x = sum(x_values[key]) / len(x_values[key])
                merged_intervals = self._merge_intervals(intervals)
                for y0, y1 in merged_intervals:
                    merged.append(("v", y0, y1, avg_x))
            
            if len(merged) == len(current_segments):
                break
            
            current_segments = merged
        
        current_segments.sort(key=lambda seg: seg[3])
        return current_segments
    
    def _merge_intervals(self, intervals: List[Tuple]) -> List[Tuple]:
        if not intervals:
            return []
        
        intervals.sort()
        merged = [intervals[0]]
        
        for current in intervals[1:]:
            last = merged[-1]
            if current[0] <= last[1] + self.merge_tolerance:
                merged[-1] = (last[0], max(last[1], current[1]))
            else:
                merged.append(current)
        
        return merged
    
    def _find_all_intersections(self, h_segments: List[Tuple], 
                               v_segments: List[Tuple]):
        # Find all intersections between horizontal and vertical segments
        intersections = set()
        naked_points = set()
        
        for i, h_seg in enumerate(h_segments):
            naked_points.add(('h', 'l', i))
            naked_points.add(('h', 'r', i))
        for i, v_seg in enumerate(v_segments):
            naked_points.add(('v', 't', i))
            naked_points.add(('v', 'b', i))
        
        for h_idx, h_seg in enumerate(h_segments):
            _, x0, x1, y = h_seg
            x_min, x_max = x0 - self.intersection_tolerance, x1 + self.intersection_tolerance
            
            for v_idx, v_seg in enumerate(v_segments):
                _, y0, y1, x = v_seg
                y_min, y_max = y0 - self.intersection_tolerance, y1 + self.intersection_tolerance
                
                if (x_min <= x <= x_max and y_min <= y <= y_max):
                    intersections.add((x, y))
                    if x < x0:
                        h_segments[h_idx] = ("h", x, x1, y)
                    elif x > x1:
                        h_segments[h_idx] = ("h", x0, x, y)
                    if y < y0:
                        v_segments[v_idx] = ("v", y, y1, x)
                    elif y > y1:
                        v_segments[v_idx] = ("v", y0, y, x)
                    
                    if x_min < x < x0 + self.intersection_tolerance:
                        naked_points.discard(('h', 'l', h_idx))
                    if x_max > x > x1 - self.intersection_tolerance:
                        naked_points.discard(('h', 'r', h_idx))
                    if y_min < y < y0 + self.intersection_tolerance:
                        naked_points.discard(('v', 't', v_idx))
                    if y_max > y > y1 - self.intersection_tolerance:
                        naked_points.discard(('v', 'b', v_idx))
        
        # print(f"  - Found {len(intersections)} intersections")
        # print(f"  - Found {len(naked_points)} naked points")
        
        # Process naked points alignment
        self._align_naked_points(naked_points, intersections, h_segments, v_segments)
        
        return intersections
    
    def _align_naked_points(self, naked_points, intersections, h_segments, v_segments):
        # Align naked points with intersections and each other
        # Step 1: Align horizontal naked points with intersections
        for orientation, position, idx in list(naked_points):
            if orientation == 'h':
                h_seg = h_segments[idx]
                _, x0, x1, y = h_seg
                x = x0 if position == 'l' else x1
                
                for ix, _ in intersections:
                    if position == 'l' and abs(ix - x) <= self.naked_point_tolerance:
                        h_segments[idx] = ("h", ix, x1, y)
                        intersections.add((ix, y))
                        naked_points.discard((orientation, position, idx))
                        break
                    elif position == 'r' and abs(ix - x) <= self.naked_point_tolerance:
                        h_segments[idx] = ("h", x0, ix, y)
                        intersections.add((ix, y))
                        naked_points.discard((orientation, position, idx))
                        break
        
        # Step 2: Align vertical naked points with intersections
        for orientation, position, idx in list(naked_points):
            if orientation == 'v':
                v_seg = v_segments[idx]
                _, y0, y1, x = v_seg
                y = y0 if position == 't' else y1
                
                for ix, iy in intersections:
                    if position == 't' and abs(iy - y) <= self.naked_point_tolerance:
                        v_segments[idx] = ("v", iy, y1, x)
                        intersections.add((x, iy))
                        naked_points.discard((orientation, position, idx))
                        break
                    elif position == 'b' and abs(iy - y) <= self.naked_point_tolerance:
                        v_segments[idx] = ("v", y0, iy, x)
                        intersections.add((x, iy))
                        naked_points.discard((orientation, position, idx))
                        break
        
        # Step 3: Align remaining naked points with each other
        self._align_naked_points_together(naked_points, intersections, h_segments, v_segments)
    
    def _align_naked_points_together(self, naked_points, intersections, h_segments, v_segments):
        # Align naked points with each other
        h_naked_groups = []
        v_naked_groups = []
        
        for orientation, position, idx in naked_points:
            if orientation == 'h':
                h_naked_groups.append((position, idx))
            else:
                v_naked_groups.append((position, idx))
        
        max_iterations = 5
        
        # Horizontal alignment
        for iteration in range(max_iterations):
            groups = defaultdict(list)
            x_values = defaultdict(list)
            bias = self.naked_point_tolerance * (max_iterations - iteration) / max_iterations
            align_flag = False
            
            for position, idx in h_naked_groups:
                h_seg = h_segments[idx]
                _, x0, x1, y = h_seg
                x = x0 if position == 'l' else x1
                biased_x = x + bias
                key = self._get_tolerance_key(biased_x)
                groups[key].append((position, idx))
                x_values[key].append(x)
            
            for key, points in groups.items():
                avg_x = sum(x_values[key]) / len(x_values[key])
                for position, idx in points:
                    h_seg = h_segments[idx]
                    _, x0, x1, y = h_seg
                    if position == 'l':
                        h_segments[idx] = ("h", avg_x, x1, y)
                    else:
                        h_segments[idx] = ("h", x0, avg_x, y)
                    intersections.add((avg_x, y))
                    align_flag = True
            
            if not align_flag:
                break
        
        # Vertical alignment
        for iteration in range(max_iterations):
            groups = defaultdict(list)
            y_values = defaultdict(list)
            bias = self.naked_point_tolerance * (max_iterations - iteration) / max_iterations
            align_flag = False
            
            for position, idx in v_naked_groups:
                v_seg = v_segments[idx]
                _, y0, y1, x = v_seg
                y = y0 if position == 't' else y1
                biased_y = y + bias
                key = self._get_tolerance_key(biased_y)
                groups[key].append((position, idx))
                y_values[key].append(y)
            
            for key, points in groups.items():
                avg_y = sum(y_values[key]) / len(y_values[key])
                for position, idx in points:
                    v_seg = v_segments[idx]
                    _, y0, y1, x = v_seg
                    if position == 't':
                        v_segments[idx] = ("v", avg_y, y1, x)
                    else:
                        v_segments[idx] = ("v", y0, avg_y, x)
                    intersections.add((x, avg_y))
                    align_flag = True
            
            if not align_flag:
                break
    
    def _detect_rectangles(self, intersections: Set[Tuple], h_segments: List[Tuple] = None, 
                          v_segments: List[Tuple] = None) -> List[Tuple]:
        # Multithreaded version of rectangle detection
        points = sorted(list(intersections))
        
        if not self.enable_multithreading or len(points) < 50:
            return self._detect_rectangles_sequential(intersections, h_segments, v_segments)
        
        rectangles = []
        left_top_points = set()
        right_bottom_points = set()
        lock = threading.Lock()
        
        def process_point_range(start_idx: int, end_idx: int) -> List[Tuple]:
            local_rectangles = []
            local_left_top = set()
            local_right_bottom = set()
            
            for i in range(start_idx, min(end_idx, len(points))):
                bottom_left = points[i]
                x1, y1 = bottom_left
                
                for j in range(i + 1, len(points)):
                    x2, y2 = points[j]
                    
                    if x2 <= x1 + self.tolerance:
                        continue
                    if y2 <= y1 + self.tolerance:
                        continue
                    
                    bottom_right = (x2, y1)
                    top_left = (x1, y2)
                    
                    if self._point_exists(bottom_right, intersections) and \
                       self._point_exists(top_left, intersections):
                        
                        if h_segments is not None and v_segments is not None:
                            bottom_edge_exists = self._edge_exists(x1, x2, y1, True, h_segments)
                            top_edge_exists = self._edge_exists(x1, x2, y2, True, h_segments)
                            left_edge_exists = self._edge_exists(y1, y2, x1, False, v_segments)
                            right_edge_exists = self._edge_exists(y1, y2, x2, False, v_segments)
                            cnt = int(bottom_edge_exists) + int(top_edge_exists) + \
                                  int(left_edge_exists) + int(right_edge_exists)
                            
                            if cnt < 3:
                                continue
                        
                        rect = ((x1, y1), (x2, y2))
                        
                        if (x1, y1) not in local_left_top and (x2, y2) not in local_right_bottom:
                            if (x2 - x1) >= self.min_box_size and (y2 - y1) >= self.min_box_size:
                                local_left_top.add((x1, y1))
                                local_right_bottom.add((x2, y2))
                                local_rectangles.append(rect)
            
            return local_rectangles, local_left_top, local_right_bottom
        
        # Divide points into chunks for parallel processing
        chunk_size = max(1, len(points) // self.max_workers)
        futures = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for i in range(0, len(points), chunk_size):
                end_idx = min(i + chunk_size, len(points))
                future = executor.submit(process_point_range, i, end_idx)
                futures.append(future)
            
            # Collect results from all futures
            for future in as_completed(futures):
                local_rects, _, _ = future.result()
                
                with lock:
                    # Merge local results into global
                    for rect in local_rects:
                        x1, y1 = rect[0]
                        x2, y2 = rect[1]
                        if (x1, y1) not in left_top_points and (x2, y2) not in right_bottom_points:
                            left_top_points.add((x1, y1))
                            right_bottom_points.add((x2, y2))
                            rectangles.append(rect)
        
        return rectangles
    
    def _detect_rectangles_sequential(self, intersections: Set[Tuple], h_segments: List[Tuple] = None, 
                                    v_segments: List[Tuple] = None) -> List[Tuple]:
        # Sequential version of _detect_rectangles
        points = sorted(list(intersections))
        rectangles = []
        left_top_points = set()
        right_bottom_points = set()
        
        for i, bottom_left in enumerate(points):
            x1, y1 = bottom_left
            
            for j in range(i + 1, len(points)):
                x2, y2 = points[j]
                
                if x2 <= x1 + self.tolerance:
                    continue
                if y2 <= y1 + self.tolerance:
                    continue
                
                bottom_right = (x2, y1)
                top_left = (x1, y2)
                
                if self._point_exists(bottom_right, intersections) and \
                   self._point_exists(top_left, intersections):
                    
                    if h_segments is not None and v_segments is not None:
                        bottom_edge_exists = self._edge_exists(x1, x2, y1, True, h_segments)
                        top_edge_exists = self._edge_exists(x1, x2, y2, True, h_segments)
                        left_edge_exists = self._edge_exists(y1, y2, x1, False, v_segments)
                        right_edge_exists = self._edge_exists(y1, y2, x2, False, v_segments)
                        cnt = int(bottom_edge_exists) + int(top_edge_exists) + \
                              int(left_edge_exists) + int(right_edge_exists)
                        
                        if cnt < 3:
                            continue
                    
                    rect = ((x1, y1), (x2, y2))
                    
                    if (x1, y1) not in left_top_points and (x2, y2) not in right_bottom_points:
                        if (x2 - x1) >= self.min_box_size and (y2 - y1) >= self.min_box_size:
                            left_top_points.add((x1, y1))
                            right_bottom_points.add((x2, y2))
                            rectangles.append(rect)
        
        return rectangles
    
    def _point_exists(self, point: Tuple[float, float], intersections: Set[Tuple]) -> bool:
        # Check if the point exists in the set of intersections
        x, y = point
        for ix, iy in intersections:
            if abs(x - ix) < self.tolerance and abs(y - iy) < self.tolerance:
                return True
        return False
    
    def _edge_exists(self, start: float, end: float, fixed_coord: float, 
                    is_horizontal: bool, segments: List[Tuple]) -> bool:
        # Check if the line segment exists in the given segments
        min_coord = min(start, end)
        max_coord = max(start, end)
        
        for seg in segments:
            if is_horizontal and seg[0] == "h":
                _, x0, x1, y = seg
                if abs(y - fixed_coord) < self.tolerance:
                    seg_min = min(x0, x1)
                    seg_max = max(x0, x1)
                    if seg_min <= min_coord + self.tolerance and \
                       seg_max >= max_coord - self.tolerance:
                        return True
            elif not is_horizontal and seg[0] == "v":
                _, y0, y1, x = seg
                if abs(x - fixed_coord) < self.tolerance:
                    seg_min = min(y0, y1)
                    seg_max = max(y0, y1)
                    if seg_min <= min_coord + self.tolerance and \
                       seg_max >= max_coord - self.tolerance:
                        return True
        
        return False
    
    # ========== Text Grouping Methods ==========
    
    def is_text_in_box(self, word: Dict, box: Tuple[float, float, float, float], 
                      use_margin: bool = False) -> bool:
        # Check if text is contained within a box.
        box_x0, box_y0, box_x1, box_y1 = box
        word_x0, word_y0, word_x1, word_y1 = word['x0'], word['y0'], word['x1'], word['y1']
        
        if use_margin:
            box_x0 -= self.text_margin
            box_y0 -= self.text_margin
            box_x1 += self.text_margin
            box_y1 += self.text_margin
        
        return (box_x0 <= word_x0 and word_x1 <= box_x1 and 
                box_y0 <= word_y0 and word_y1 <= box_y1)
    
    def find_containing_box(self, word: Dict, boxes: List[Tuple]) -> Optional[Tuple]:
        # Find the smallest box containing the word.
        exact_boxes = [box for box in boxes if self.is_text_in_box(word, box, False)]
        if exact_boxes:
            return min(exact_boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
        
        margin_boxes = [box for box in boxes if self.is_text_in_box(word, box, True)]
        if margin_boxes:
            return min(margin_boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
        
        return None
    
    def group_text_by_boxes(self, words: List[Dict], boxes: List[Tuple]) -> Dict:
        # Group words by their containing boxes.
        grouped_text = defaultdict(list)
        ungrouped_text = []
        
        for word in words:
            containing_box = self.find_containing_box(word, boxes)
            
            if containing_box:
                grouped_text[containing_box].append(word)
            else:
                ungrouped_text.append(word)
        
        return {
            'grouped': dict(grouped_text),
            'ungrouped': ungrouped_text
        }
    
    def group_by_y_position(self, words: List[Dict]) -> List[List[Dict]]:
        # Group words by their y-position (same line).
        if not words:
            return []
        
        sorted_words = sorted(words, key=lambda w: (w['y0'], w['x0']))
        
        lines = []
        current_line = [sorted_words[0]]
        current_y = (sorted_words[0]['y0'] + sorted_words[0]['y1']) / 2
        
        for word in sorted_words[1:]:
            word_y = (word['y0'] + word['y1']) / 2
            
            if abs(word_y - current_y) <= self.y_tolerance:
                current_line.append(word)
            else:
                lines.append(current_line)
                current_line = [word]
                current_y = word_y
        
        lines.append(current_line)
        return lines
    
    def find_vertical_alignments(self, lines: List[List[Dict]]) -> List[Dict]:
        # Find vertical alignments that suggest multi-line text blocks.
        alignments = []
        
        if len(lines) < 2:
            return alignments
        
        i = 0
        while i < len(lines) - 1:
            alignment_group = [i]
            first_line_x = min(word['x0'] for word in lines[i])
            line_spacings = []
            
            j = i + 1
            while j < len(lines):
                line_x = min(word['x0'] for word in lines[j]) if lines[j] else float('inf')
                
                if abs(line_x - first_line_x) <= self.x_tolerance:
                    prev_line_idx = alignment_group[-1]
                    prev_line_bottom = max(word['y1'] for word in lines[prev_line_idx])
                    curr_line_top = min(word['y0'] for word in lines[j])
                    spacing = curr_line_top - prev_line_bottom
                    
                    if len(line_spacings) >= 2:
                        avg_spacing = sum(line_spacings) / len(line_spacings)
                        if spacing > avg_spacing * 2.0 and spacing > self.y_tolerance:
                            break
                    
                    alignment_group.append(j)
                    if spacing > 0:
                        line_spacings.append(spacing)
                    j += 1
                else:
                    break
            
            if len(alignment_group) >= 2:
                all_words = []
                for idx in alignment_group:
                    all_words.extend(lines[idx])
                
                x0 = min(w['x0'] for w in all_words)
                x1 = max(w['x1'] for w in all_words)
                y0 = min(w['y0'] for w in all_words)
                y1 = max(w['y1'] for w in all_words)
                
                alignments.append({
                    'line_indices': alignment_group,
                    'bounds': (x0, y0, x1, y1),
                    'lines': [lines[idx] for idx in alignment_group]
                })
                
                i = j
            else:
                i += 1
        
        return alignments
    
    def aggregate_multi_line_text(self, alignment: Dict) -> Dict:
        # Aggregate text from a multi-line alignment into a single text block.
        aggregated_text = []
        
        for line in alignment['lines']:
            sorted_line = sorted(line, key=lambda w: w['x0'])
            line_text = ' '.join(w['text'] for w in sorted_line)
            aggregated_text.append(line_text)
        
        full_text = '\n'.join(aggregated_text)
        
        return {
            'text': full_text,
            'bounds': alignment['bounds'],
            'line_count': len(alignment['lines']),
            'word_count': sum(len(line) for line in alignment['lines'])
        }
    
    def aggregate_box_text(self, box_words: List[Dict]) -> Dict:
        # Process all words in a box to find and aggregate multi-line text.
        lines = self.group_by_y_position(box_words)
        alignments = self.find_vertical_alignments(lines)
        
        multi_line_blocks = []
        used_line_indices = set()
        
        for alignment in alignments:
            multi_line_blocks.append(self.aggregate_multi_line_text(alignment))
            used_line_indices.update(alignment['line_indices'])
        
        isolated_words = []
        for i, line in enumerate(lines):
            if i not in used_line_indices:
                isolated_words.extend(line)
        
        return {
            'multi_line_blocks': multi_line_blocks,
            'isolated_words': isolated_words,
            'total_lines': len(lines),
            'aligned_lines': len(used_line_indices)
        }
    
    # ========== Semantic Analysis Methods ==========
    
    def is_mostly_numbers_and_symbols(self, text):
        # Check if text contains more than 80% numbers and symbols.
        if not text:
            return True
        
        letter_count = sum(1 for char in text if char.isalpha())
        total_count = len(text)
        non_letter_percentage = (total_count - letter_count) / total_count
        
        return non_letter_percentage > 0.8
    
    def validate_multiline_aggregations_batch(self, aggregated_texts):
        # Validate multiple aggregated texts in a batch using OpenAI.
        if not aggregated_texts:
            return []
        
        if not self.client:
            # If no OpenAI client, use rule-based validation only
            return [not self.is_mostly_numbers_and_symbols(text) for text in aggregated_texts]
        
        results = []
        
        for i in range(0, len(aggregated_texts), self.batch_size):
            batch = aggregated_texts[i:i + self.batch_size]
            batch_results = []
            filtered_texts = []
            filtered_indices = []
            
            for idx, text in enumerate(batch):
                if self.is_mostly_numbers_and_symbols(text):
                    batch_results.append((idx, False))
                else:
                    filtered_texts.append(text)
                    filtered_indices.append(idx)
            
            if filtered_texts:
                instruction = "Given a list of texts, for each text, if it can be a valid and independent table cell or a valid paragraph, return 'yes'. Otherwise, return no. For table cell, repetition of words of similar meaning should be rejected. Do not add any explanations, only return yes or no for each text."
                
                context = ""
                for text in filtered_texts:
                    cleaned_text = text.replace('\n', ' ')
                    context += f"\n\"{cleaned_text}\""
                
                message_content = instruction + context
                
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": message_content}],
                    temperature=0
                )
                
                response_text = response.choices[0].message.content
                lines = response_text.strip().split('\n')
                llm_results = []
                for line in lines:
                    if line.strip():
                        llm_results.append('yes' in line.lower())
                
                for idx, result in zip(filtered_indices, llm_results[:len(filtered_indices)]):
                    batch_results.append((idx, result))
            
            batch_results.sort(key=lambda x: x[0])
            for _, result in batch_results:
                results.append(result)
        
        return results
    
    def process_aggregated_text(self, aggregated_data):
        # Process aggregated text data and validate multi-line blocks.
        processed_results = {
            'boxes': {},
            'statistics': {
                'total_multiline_blocks': 0,
                'validated_blocks': 0,
                'rejected_blocks': 0
            }
        }
        
        all_multiline_texts = []
        box_block_mapping = []
        
        for box_str, box_result in aggregated_data['boxes'].items():
            for block_idx, block in enumerate(box_result['multi_line_blocks']):
                all_multiline_texts.append(block['text'])
                box_block_mapping.append((box_str, block_idx))
        
        if all_multiline_texts:
            validation_results = self.validate_multiline_aggregations_batch(all_multiline_texts)
            
            for idx, (is_valid, (box_str, block_idx)) in enumerate(zip(validation_results, box_block_mapping)):
                if box_str not in processed_results['boxes']:
                    processed_results['boxes'][box_str] = {
                        'validated_multiline_blocks': [],
                        'rejected_blocks': [],
                        'isolated_words': aggregated_data['boxes'][box_str]['isolated_words']
                    }
                
                block = aggregated_data['boxes'][box_str]['multi_line_blocks'][block_idx]
                
                if is_valid:
                    processed_results['boxes'][box_str]['validated_multiline_blocks'].append(block)
                    processed_results['statistics']['validated_blocks'] += 1
                else:
                    processed_results['boxes'][box_str]['rejected_blocks'].append(block)
                    processed_results['statistics']['rejected_blocks'] += 1
                
                processed_results['statistics']['total_multiline_blocks'] += 1
        
        for box_str, box_result in aggregated_data['boxes'].items():
            if box_str not in processed_results['boxes']:
                processed_results['boxes'][box_str] = {
                    'validated_multiline_blocks': [],
                    'rejected_blocks': [],
                    'isolated_words': box_result['isolated_words']
                }
        
        return processed_results
    
    # ========== Main Pipeline Method ==========
    
    def process_document(self, horizontal_segments: List[Tuple], 
                        vertical_segments: List[Tuple], 
                        words: List[Dict]) -> Dict:
        """
        Process a document through the entire pipeline.
        
        Args:
            horizontal_segments: List of horizontal line segments
            vertical_segments: List of vertical line segments
            words: List of word dictionaries with text and position info
            
        Returns:
            Dict containing:
            - rectangles: Detected boxes
            - grouped_text: Text grouped by boxes
            - aggregated_text: Multi-line text aggregation results
            - semantic_analysis: Validated text blocks
        """
        start_time = time.time()
        # print("=== Starting Multi Row Processing Pipeline ===")
        
        # Step 1: Find rectangles (boxes)
        # print("\n--- Step 1: Box Detection ---")
        step_start = time.time()
        rectangles = self.find_rectangles(horizontal_segments, vertical_segments)
        self.performance_stats['box_detection_time'] = time.time() - step_start
        # print(f"Found {len(rectangles)} rectangles (took {self.performance_stats['box_detection_time']:.3f}s)")
        
        # Convert rectangle format for text grouping
        boxes = [(rect[0][0], rect[0][1], rect[1][0], rect[1][1]) for rect in rectangles]
        
        # Step 2: Group text by boxes
        # print("\n--- Step 2: Text Grouping ---")
        step_start = time.time()
        grouping_result = self.group_text_by_boxes(words, boxes)
        self.performance_stats['text_grouping_time'] = time.time() - step_start
        # print(f"Grouped text into {len(grouping_result['grouped'])} boxes (took {self.performance_stats['text_grouping_time']:.3f}s)")
        # print(f"Ungrouped words: {len(grouping_result['ungrouped'])}")
        
        # Step 3: Aggregate multi-line text within boxes
        # print("\n--- Step 3: Multi-line Text Aggregation ---")
        step_start = time.time()
        aggregated_results = {
            'boxes': {},
            'statistics': {
                'total_boxes': 0,
                'boxes_with_multiline': 0,
                'total_multiline_blocks': 0,
                'total_isolated_words': 0
            }
        }
        
        grouped_items = list(grouping_result['grouped'].items())
        
        if self.enable_multithreading and len(grouped_items) > 1:
            def process_single_box(box_item):
                box, box_words = box_item
                box_result = self.aggregate_box_text(box_words)
                return str(box), box_result
            
            with ThreadPoolExecutor(max_workers=min(self.max_workers, len(grouped_items))) as executor:
                future_to_box = {executor.submit(process_single_box, item): item for item in grouped_items}
                
                for future in as_completed(future_to_box):
                    box_str, box_result = future.result()
                    aggregated_results['boxes'][box_str] = box_result
                    
                    aggregated_results['statistics']['total_boxes'] += 1
                    if box_result['multi_line_blocks']:
                        aggregated_results['statistics']['boxes_with_multiline'] += 1
                        aggregated_results['statistics']['total_multiline_blocks'] += len(box_result['multi_line_blocks'])
                    aggregated_results['statistics']['total_isolated_words'] += len(box_result['isolated_words'])
        else:
            for box, box_words in grouped_items:
                box_result = self.aggregate_box_text(box_words)
                aggregated_results['boxes'][str(box)] = box_result
                
                aggregated_results['statistics']['total_boxes'] += 1
                if box_result['multi_line_blocks']:
                    aggregated_results['statistics']['boxes_with_multiline'] += 1
                    aggregated_results['statistics']['total_multiline_blocks'] += len(box_result['multi_line_blocks'])
                aggregated_results['statistics']['total_isolated_words'] += len(box_result['isolated_words'])
        
        self.performance_stats['text_aggregation_time'] = time.time() - step_start
        # print(f"Found {aggregated_results['statistics']['total_multiline_blocks']} multi-line blocks (took {self.performance_stats['text_aggregation_time']:.3f}s)")
        
        # Step 4: Semantic analysis
        # print("\n--- Step 4: Semantic Analysis ---")
        step_start = time.time()
        semantic_results = self.process_aggregated_text(aggregated_results)
        self.performance_stats['semantic_analysis_time'] = time.time() - step_start
        # print(f"Validated blocks: {semantic_results['statistics']['validated_blocks']} (took {self.performance_stats['semantic_analysis_time']:.3f}s)")
        # print(f"Rejected blocks: {semantic_results['statistics']['rejected_blocks']}")
        
        # Calculate total time
        self.performance_stats['total_time'] = time.time() - start_time
        
        # Compile final results
        return {
            'rectangles': rectangles,
            'grouped_text': grouping_result,
            'aggregated_text': aggregated_results,
            'semantic_analysis': semantic_results,
            'pipeline_summary': {
                'total_rectangles': len(rectangles),
                'total_grouped_boxes': len(grouping_result['grouped']),
                'total_ungrouped_words': len(grouping_result['ungrouped']),
                'total_multiline_blocks': aggregated_results['statistics']['total_multiline_blocks'],
                'validated_blocks': semantic_results['statistics']['validated_blocks'],
                'rejected_blocks': semantic_results['statistics']['rejected_blocks']
            }
        }
    
    def get_final_phrases(self, process_document_results: Dict) -> List[Dict]:
        """
        Extract final phrases from process_document results, merging validated multi-line blocks
        and keeping individual phrases separate.
        
        Args:
            process_document_results: Output from process_document method
            
        Returns:
            List of dictionaries, each containing:
            - text: The phrase text
            - x0, x1, top, bottom: Bounding box coordinates
        """
        final_phrases = []
        
        # Process grouped text in boxes
        semantic_results = process_document_results.get('semantic_analysis', {})
        grouped_text = process_document_results.get('grouped_text', {})
        
        # Process each box
        for box_str, box_data in semantic_results.get('boxes', {}).items():
            # Process validated multi-line blocks (merge them)
            for block in box_data.get('validated_multiline_blocks', []):
                # For multi-line blocks, use the bounds from the block
                x0, y0, x1, y1 = block['bounds']
                # Replace '\n' with ' '
                text = block['text'].replace('\n', ' ')
                final_phrases.append({
                    'text': text,
                    'x0': x0,
                    'x1': x1,
                    'top': y0,
                    'bottom': y1,
                    'y0': y0,
                    'y1': y1
                })
            
            # Process rejected blocks - add each word individually
            for block in box_data.get('rejected_blocks', []):
                # Find the original words from this block
                # We need to extract individual words from the rejected multi-line block
                # Parse the box string to get box coordinates
                box_tuple = eval(box_str)  # Convert string representation back to tuple
                box_words = grouped_text['grouped'].get(box_tuple, [])
                
                # Find words that were part of this rejected block
                block_bounds = block['bounds']
                for word in box_words:
                    # Check if word is within the rejected block bounds
                    if (block_bounds[0] <= word['x0'] <= block_bounds[2] and
                        block_bounds[1] <= word['y0'] <= block_bounds[3]):
                        final_phrases.append({
                            'text': word['text'],
                            'x0': word['x0'],
                            'x1': word['x1'],
                            'top': word['y0'],
                            'bottom': word['y1'],
                            'y0': word['y0'],
                            'y1': word['y1']
                        })
            
            # Process isolated words (not part of any multi-line block)
            for word in box_data.get('isolated_words', []):
                final_phrases.append({
                    'text': word['text'],
                    'x0': word['x0'],
                    'x1': word['x1'],
                    'top': word['y0'],
                    'bottom': word['y1'],
                    'y0': word['y0'],
                    'y1': word['y1']
                })
        
        # Process ungrouped text (not in any box)
        for word in grouped_text.get('ungrouped', []):
            final_phrases.append({
                'text': word['text'],
                'x0': word['x0'],
                'x1': word['x1'],
                'top': word['y0'],
                'bottom': word['y1'],
                'y0': word['y0'],
                'y1': word['y1']
            })
        
        # Sort by position (top to bottom, left to right)
        final_phrases = utils_extract.sort_words_by_reading_order(final_phrases)
        
        return final_phrases

# Example usage
if __name__ == "__main__":
    # Initialize pipeline
    pipeline = MultiRowProcessPipeline()
    
    # Example data
    h_segments = [
        ("h", 0.0, 10.0, 0.0),
        ("h", 0.0, 10.0, 5.0),
        ("h", 0.0, 10.0, 10.0),
        ("h", 3.0, 7.0, 2.5),
        ("h", 3.0, 7.0, 7.5)
    ]
    
    v_segments = [
        ("v", 0.0, 10.0, 0.0),
        ("v", 0.0, 10.0, 5.0),
        ("v", 0.0, 10.0, 10.0),
        ("v", 2.5, 7.5, 3.0),
        ("v", 2.5, 7.5, 7.0)
    ]
    
    # Example words (you would get these from PDF extraction)
    words = [
        {'text': 'Hello', 'x0': 1, 'y0': 1, 'x1': 2, 'y1': 1.5},
        {'text': 'World', 'x0': 2.5, 'y0': 1, 'x1': 3.5, 'y1': 1.5},
        {'text': 'This', 'x0': 1, 'y0': 2, 'x1': 2, 'y1': 2.5},
        {'text': 'is', 'x0': 2.2, 'y0': 2, 'x1': 2.7, 'y1': 2.5},
        {'text': 'a', 'x0': 2.9, 'y0': 2, 'x1': 3.2, 'y1': 2.5},
        {'text': 'test', 'x0': 3.4, 'y0': 2, 'x1': 4.2, 'y1': 2.5}
    ]
    
    # Process document
    results = pipeline.process_document(h_segments, v_segments, words)
    
    print("\n=== Pipeline Summary ===")
    for key, value in results['pipeline_summary'].items():
        print(f"{key}: {value}")