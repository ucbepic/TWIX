def PROMPT_RECORD_SEPARATION(ocr_csv_path: str, template_json: str) -> str:
    return f"""Create a Python script called `record_separation.py` that groups OCR words from a multi-page document into logical records using the TWIX record separation algorithm (Section 4.1 of the TWIX paper).

Context:
- A sample OCR CSV file is at: {ocr_csv_path}
  Columns: id, page, x0, top, x1, bottom, text
  `id` is a globally unique integer assigned to each extracted word across the whole document.
- The document template defines the following blocks (nodes in the template tree T):
{template_json}

ALGORITHM (TWIX paper, Section 4.1 — Record Separation):

Definitions:
- A "row" is a list of words that are horizontally aligned (their vertical bounding boxes
  overlap on the y-axis: y_i1 <= y_j2 AND y_i2 >= y_j1).
- A "block" B is a sequence of consecutive rows.
- A node v in the template is "visited" by block B, denoted vis(v, B) = True, iff
  ALL fields of v appear in B.phrases, i.e. v.fields ⊆ B.phrases.
- A record is the SMALLEST consecutive block of rows that visits EVERY node in the
  template tree T at least once, considered in pre-order traversal.

The template nodes are processed in pre-order traversal order (the order given in
{template_json}, treating the list as a flat pre-order sequence of non-root nodes).

Record-separation procedure (per Example 6 of the paper):
1. Read all OCR words and sort globally by (page ASC, top ASC, x0 ASC) so words appear
   in natural reading order. The global `id` reflects this order — preserve it.
2. Group words into ROWS using horizontal alignment: scan words in order of id; merge
   word p into an existing row r iff p is horizontally aligned (y-overlap) with EVERY
   word already in r. Otherwise start a new row. A word that aligns with multiple
   open rows joins the FIRST one it aligns with. Rows are page-local (do not merge
   rows across pages).
3. Maintain a "current record" accumulator that is a growing list of consecutive rows.
   Track `visited`: a set of template node indices that have been visited at least
   once since the current record started.
4. Scan rows in ascending order across the whole document. For each new row r appended
   to the current record:
     a. Recompute B.phrases as the union of all word texts in the current record's
        rows so far.
     b. For each template node v, check vis(v, current_record) = (v.fields ⊆ B.phrases).
     c. Update `visited` with any newly-visited nodes.
     d. After updating, check whether appending r caused a node v* that is ALREADY in
        `visited` to be visited AGAIN by r alone (i.e. v*.fields ⊆ phrases_of(r) and
        v* was already in `visited` BEFORE this row was added) AND all nodes in T are
        in `visited`. If so:
          - Close the current record WITHOUT r (the previous accumulated rows form
            the completed record).
          - Start a NEW current record beginning with r.
          - Reset `visited` and re-evaluate visits for the new record using r's phrases.
   This implements the paper's rule: "when a node is visited the second time AND all
   nodes have been visited at least once, that marks the start of a new record."
5. After scanning all rows, flush the final accumulated record (even if not all nodes
   were visited — append whatever remains as the last record).
6. Assign every word in the document to exactly one record, based on which record's
   rows contain it.

Field-matching notes:
- Compare field strings to word `text` case-insensitively and after stripping
  surrounding whitespace and trailing punctuation (`:`, `.`, `,`).
- A multi-word field (e.g. "Type of Complaint") is considered present in B.phrases iff
  its constituent tokens appear as a contiguous run of words within some row of B,
  in order. (Implement a simple n-gram scan over each row's word texts.)

The script must define a main function with this exact signature:
  def main(inputpath: str, out_path: str) -> None
  - `inputpath`: path to the OCR CSV file to process.
  - `out_path`: path to the folder where `record_separation.json` must be written.

Output: write `<out_path>/record_separation.json` with this exact structure:
   {{
     "records": [
       {{
         "record_id": "<index>",
         "pages": [
           {{
             "page": <int>,
             "y_start": <float>,
             "y_end": <float>,
             "words": [
               {{"id": <int>, "x0": <float>, "top": <float>, "x1": <float>, "bottom": <float>, "text": <str>}},
               ...
             ]
           }},
           ...
         ]
       }},
       ...
     ]
   }}
   Each record contains one entry per page it spans. `y_start` / `y_end` are the
   top / bottom coordinates of the record's words on that page. Words within each
   page entry must be sorted by their global `id`.

Print a summary to stdout: one line per record showing its id, the page range it
spans, and which template node indices were visited inside it.

The script must also contain:
  if __name__ == "__main__":
      import sys
      main(sys.argv[1], sys.argv[2])

Use only the Python standard library (csv, json, os, collections). Do not install any packages.
Always open files with encoding="utf-8", errors="replace".
"""
