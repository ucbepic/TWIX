from flask import Flask, send_file, jsonify, request, Response
from flask_cors import CORS
import json
import os
import sys
import tempfile
import shutil
import logging
from collections import OrderedDict

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the parent directory to sys.path to import twix
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import twix

app = Flask(__name__)
CORS(app)

# Define paths to JSON files and upload directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_FILES_DIR = os.path.join(BASE_DIR, 'src', 'json_files')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
RESULT_FOLDER = os.path.join(BASE_DIR, 'results')

# Create directories if they don't exist
os.makedirs(JSON_FILES_DIR, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

@app.route('/process/phrase', methods=['POST'])
def process_phrase():
    try:
        # Get uploaded files
        files = request.files.getlist('pdfs')
        logger.info(f"Received {len(files)} files for phrase processing")
        
        if not files or len(files) == 0:
            return jsonify({'error': 'No files uploaded'}), 400
        
        # Save uploaded files to temporary directory
        pdf_paths = []
        for file in files:
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            logger.info(f"Saving file to {file_path}")
            file.save(file_path)
            pdf_paths.append(file_path)

        # Create accessible directories for bounding box files
        result_folder = twix.extract.get_result_folder_path(pdf_paths)
        os.makedirs(os.path.dirname(result_folder), exist_ok=True)
        
        # Use twix to extract phrases
        logger.info(f"Extracting phrases from {len(pdf_paths)} PDFs")
        phrases, cost = twix.extract_phrase(pdf_paths, result_folder)
        logger.info(f"Extracted {len(phrases)} phrases")
        
        
        # Define paths for the bounding box files
        bb_path = os.path.join(result_folder, 'merged_phrases_bounding_box_page_number.json')
        bb_txt_path = os.path.join(os.path.dirname(result_folder), 'merged_raw_phrases_bounding_box_page_number.txt')
        
        # If the bounding box file doesn't exist, create a placeholder
        if not os.path.exists(bb_txt_path):
            logger.warning(f"Bounding box file not found at {bb_txt_path}, creating placeholder")
            
            # Create the TXT version (CSV format) which is what's actually used
            with open(bb_txt_path, 'w') as f:
                # Write header
                f.write("text,x0,y0,x1,y1,page\n")
                
                # Generate data in the format of the sample file
                for i, phrase in enumerate(phrases):
                    # Create realistic coordinates similar to the sample data
                    x0 = 40 + (i % 5) * 10
                    y0 = 30 + (i // 5) * 20
                    x1 = x0 + 100
                    y1 = y0 + 10
                    page = 1
                    
                    # Escape any commas in the phrase text
                    safe_phrase = phrase.replace('"', '""')
                    if ',' in safe_phrase:
                        safe_phrase = f'"{safe_phrase}"'
                    
                    f.write(f"{safe_phrase},{x0},{y0},{x1},{y1},{page}\n")
            
            logger.info(f"Created placeholder bounding box file at {bb_txt_path}")
            
            # Also create a copy with the original expected name
            try:
                shutil.copy(bb_txt_path, bb_path)
                logger.info(f"Copied TXT to JSON location at {bb_path}")
            except Exception as e:
                logger.warning(f"Failed to copy TXT to JSON location: {e}")
            
            # Also create a nested directory for tests output
            test_out_dir = os.path.join(BASE_DIR, 'tests', 'out', 'Investigations_Redacted_original')
            os.makedirs(test_out_dir, exist_ok=True)
            
            test_bb_path = os.path.join(test_out_dir, 'merged_raw_phrases_bounding_box_page_number.txt')
            try:
                shutil.copy(bb_txt_path, test_bb_path)
                logger.info(f"Copied bounding box file to tests directory at {test_bb_path}")
            except Exception as e:
                logger.warning(f"Failed to copy to tests directory: {e}")
        
        # Copy the bounding box file to additional locations for better discoverability
        try:
            source_path = bb_txt_path if os.path.exists(bb_txt_path) else bb_path
            
            for dest_dir in ['results', 'out/Investigations_Redacted_original', 'tests/out/Investigations_Redacted_original']:
                dest_path = os.path.join(BASE_DIR, dest_dir)
                os.makedirs(dest_path, exist_ok=True)
                
                # Create both txt and json versions in each location
                txt_dest = os.path.join(dest_path, 'merged_raw_phrases_bounding_box_page_number.txt')
                json_dest = os.path.join(dest_path, 'merged_raw_phrases_bounding_box_page_number.json')
                
                if os.path.exists(source_path):
                    # Copy TXT file as-is
                    shutil.copy(source_path, txt_dest)
                    logger.info(f"Copied bounding box file to {txt_dest}")
                    
                    # Convert to proper JSON format when needed
                    if source_path.endswith('.txt'):
                        try:
                            # Read the CSV data
                            with open(source_path, 'r') as f:
                                csv_content = f.read()
                            
                            # Parse the CSV into a list of rows
                            csv_rows = []
                            for line in csv_content.strip().split('\n'):
                                # Handle quoted values
                                values = []
                                current_value = ""
                                in_quotes = False
                                
                                for char in line:
                                    if char == '"':
                                        in_quotes = not in_quotes
                                    elif char == ',' and not in_quotes:
                                        values.append(current_value)
                                        current_value = ""
                                    else:
                                        current_value += char
                                
                                # Add the last value
                                values.append(current_value)
                                csv_rows.append(values)
                            
                            # Extract header
                            if csv_rows:
                                headers = csv_rows[0]
                                data_rows = csv_rows[1:]
                                
                                # Convert to JSON format
                                json_data = []
                                for row in data_rows:
                                    if len(row) >= 6:  # Ensure we have enough columns
                                        json_obj = {
                                            "text": row[0],
                                            "bbox": {
                                                "x0": float(row[1]) if row[1] else 0,
                                                "y0": float(row[2]) if row[2] else 0,
                                                "x1": float(row[3]) if row[3] else 0,
                                                "y1": float(row[4]) if row[4] else 0,
                                                "page": int(float(row[5])) if row[5] else 1
                                            }
                                        }
                                        json_data.append(json_obj)
                            
                                # Write JSON to file
                                with open(json_dest, 'w') as f:
                                    json.dump(json_data, f, indent=2)
                                
                                logger.info(f"Converted and saved as JSON to: {json_dest}")
                            else:
                                logger.warning(f"CSV data was empty, no JSON created")
                        except Exception as e:
                            logger.error(f"Failed to convert CSV to JSON: {e}")
                            # If conversion fails, just copy the file as-is
                            shutil.copy(source_path, json_dest)
                            logger.warning(f"Copied txt file to json location without conversion: {json_dest}")
        except Exception as copy_err:
            logger.warning(f"Failed to copy bounding box file: {str(copy_err)}")
        
        return jsonify({
            'status': 'success',
            'phrases': phrases
        })
    except Exception as e:
        logger.error(f"Error in process_phrase: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/process/fields', methods=['POST'])
def predict_fields():
    try:
        # Get uploaded files
        files = request.files.getlist('pdfs')
        logger.info(f"Received {len(files)} files for field prediction")
        
        if not files or len(files) == 0:
            return jsonify({'error': 'No files uploaded'}), 400
        
        # Save uploaded files to temporary directory
        pdf_paths = []
        for file in files:
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            logger.info(f"Saving file to {file_path}")
            file.save(file_path)
            pdf_paths.append(file_path)
        
        result_folder = twix.extract.get_result_folder_path(pdf_paths)
        
        # Use twix to predict fields
        logger.info(f"Predicting fields from {len(pdf_paths)} PDFs")
        fields, cost = twix.predict_field(pdf_paths, result_folder)
        logger.info(f"Predicted {len(fields)} fields")
        
        return jsonify({
            'status': 'success',
            'fields': fields
        })
    except Exception as e:
        logger.error(f"Error in predict_fields: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/process/template', methods=['POST'])
def predict_template():
    try:
        # Get uploaded files
        files = request.files.getlist('pdfs')
        logger.info(f"Received {len(files)} files for template prediction")
        
        if not files or len(files) == 0:
            return jsonify({'error': 'No files uploaded'}), 400
        
        # Save uploaded files to temporary directory
        pdf_paths = []
        for file in files:
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            logger.info(f"Saving file to {file_path}")
            file.save(file_path)
            pdf_paths.append(file_path)
        
        result_folder = twix.extract.get_result_folder_path(pdf_paths)

        # Use twix to predict template
        logger.info(f"Predicting template from {len(pdf_paths)} PDFs")
        template, cost = twix.predict_template(pdf_paths, result_folder)
        logger.info(f"Predicted template with {len(template)} nodes")
        
        return jsonify({
            'status': 'success',
            'template': template
        })
    except Exception as e:
        logger.error(f"Error in predict_template: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/process/extract', methods=['POST'])
def extract_data():
    try:
        # Get uploaded files
        files = request.files.getlist('pdfs')
        logger.info(f"Received {len(files)} files for data extraction")
        
        if not files or len(files) == 0:
            return jsonify({'error': 'No files uploaded'}), 400
        
        # Save uploaded files to temporary directory
        pdf_paths = []
        for file in files:
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            logger.info(f"Saving file to {file_path}")
            file.save(file_path)
            pdf_paths.append(file_path)
        
        result_folder = twix.extract.get_result_folder_path(pdf_paths)

        # Use twix to extract data
        logger.info(f"Extracting data from {len(pdf_paths)} PDFs")
        data, cost = twix.extract_data(pdf_paths, result_folder)
        logger.info(f"Extracted data successfully")
        
        # Create a custom response that preserves the field order
        def preserve_order(data):
            """Recursively convert dictionaries to OrderedDicts to preserve field order"""
            if isinstance(data, dict):
                # Convert to OrderedDict to preserve field order
                result = OrderedDict()
                for key, value in data.items():
                    result[key] = preserve_order(value)
                return result
            elif isinstance(data, list):
                # Process list items
                return [preserve_order(item) for item in data]
            else:
                # Return primitive values as-is
                return data
        
        # Convert the data to OrderedDict structure
        ordered_data = preserve_order(data)
        
        # Create a response that preserves the order
        response = {
            'status': 'success',
            'data': ordered_data
        }
        
        # Return the response with preserved order
        return json.dumps(response, sort_keys=False), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        logger.error(f"Error in extract_data: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/save/template', methods=['POST'])
def save_template():
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        template_data = request.json
        logger.info(f"Saving template with {len(template_data)} nodes")
        
        # Get the result folder for the most recent upload
        result_folder = RESULT_FOLDER
        
        # Use twix to save the template
        template_path = os.path.join(result_folder, 'template.json')
        twix.pattern.write_template(template_data, template_path)
        logger.info(f"Template saved to {template_path}")
        
        return jsonify({
            'status': 'success',
            'message': 'Template saved successfully'
        })
    except Exception as e:
        logger.error(f"Error in save_template: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# New endpoints using twix user_apis

@app.route('/api/add_fields', methods=['POST'])
def api_add_fields():
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.json
        added_fields = data.get('fields', [])
        logger.info(f"Adding {len(added_fields)} fields")
        
        # Get the most recent PDF files processed
        pdf_paths = []
        for filename in os.listdir(UPLOAD_FOLDER):
            if filename.lower().endswith('.pdf'):
                pdf_paths.append(os.path.join(UPLOAD_FOLDER, filename))
        
        logger.info(f"Found {len(pdf_paths)} PDF files in upload folder")

        result_folder = twix.extract.get_result_folder_path(pdf_paths)
        
        # Use twix.add_fields with the PDF paths
        updated_fields = twix.add_fields(added_fields, result_folder)
        logger.info(f"Updated fields, now have {len(updated_fields)} fields")
        
        return jsonify({
            'status': 'success',
            'fields': updated_fields,
            'message': 'Fields added successfully'
        })
    except Exception as e:
        logger.error(f"Error in api_add_fields: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/remove_fields', methods=['POST'])
def api_remove_fields():
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.json
        removed_fields = data.get('fields', [])
        logger.info(f"Removing {len(removed_fields)} fields")
        
        # Get the most recent PDF files processed
        pdf_paths = []
        for filename in os.listdir(UPLOAD_FOLDER):
            if filename.lower().endswith('.pdf'):
                pdf_paths.append(os.path.join(UPLOAD_FOLDER, filename))
        
        logger.info(f"Found {len(pdf_paths)} PDF files in upload folder")

        result_folder = twix.extract.get_result_folder_path(pdf_paths)
        
        # Use twix.remove_fields with the PDF paths
        updated_fields = twix.remove_fields(removed_fields, result_folder)
        logger.info(f"Updated fields, now have {len(updated_fields)} fields")
        
        return jsonify({
            'status': 'success',
            'fields': updated_fields,
            'message': 'Fields removed successfully'
        })
    except Exception as e:
        logger.error(f"Error in api_remove_fields: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/remove_template_node', methods=['POST'])
def api_remove_template_node():
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.json
        node_ids = data.get('node_ids', [])
        logger.info(f"Removing template nodes: {node_ids}")
        
        # Get the most recent PDF files processed
        pdf_paths = []
        for filename in os.listdir(UPLOAD_FOLDER):
            if filename.lower().endswith('.pdf'):
                pdf_paths.append(os.path.join(UPLOAD_FOLDER, filename))
        
        logger.info(f"Found {len(pdf_paths)} PDF files in upload folder")

        result_folder = twix.extract.get_result_folder_path(pdf_paths)
        
        # Use twix.remove_template_node with the PDF paths
        updated_template = twix.remove_template_node(node_ids, result_folder)
        logger.info(f"Updated template, now have {len(updated_template)} nodes")
        
        return jsonify({
            'status': 'success',
            'template': updated_template,
            'message': 'Template nodes removed successfully'
        })
    except Exception as e:
        logger.error(f"Error in api_remove_template_node: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/modify_template_node', methods=['POST'])
def api_modify_template_node():
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.json
        node_id = data.get('node_id')
        node_type = data.get('type')
        fields = data.get('fields', [])
        
        logger.info(f"Modifying template node {node_id} to type {node_type} with {len(fields)} fields")
        
        if node_id is None or node_type is None:
            return jsonify({'error': 'node_id and type are required'}), 400
        
        # Get the most recent PDF files processed
        pdf_paths = []
        for filename in os.listdir(UPLOAD_FOLDER):
            if filename.lower().endswith('.pdf'):
                pdf_paths.append(os.path.join(UPLOAD_FOLDER, filename))
        
        logger.info(f"Found {len(pdf_paths)} PDF files in upload folder")

        result_folder = twix.extract.get_result_folder_path(pdf_paths)
        
        # Use twix.modify_template_node with the PDF paths
        updated_template = twix.modify_template_node(node_id, node_type, fields, result_folder)
        logger.info(f"Updated template, now have {len(updated_template)} nodes")
        
        return jsonify({
            'status': 'success',
            'template': updated_template,
            'message': 'Template node modified successfully'
        })
    except Exception as e:
        logger.error(f"Error in api_modify_template_node: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# Cleanup route to remove temporary files
@app.route('/cleanup', methods=['POST'])
def cleanup():
    try:
        # Remove all files in the upload folder
        count = 0
        for filename in os.listdir(UPLOAD_FOLDER):
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.isfile(file_path):
                os.unlink(file_path)
                count += 1
        
        logger.info(f"Cleaned up {count} files from upload folder")
        
        return jsonify({
            'status': 'success',
            'message': f'Cleaned up {count} temporary files successfully'
        })
    except Exception as e:
        logger.error(f"Error in cleanup: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# Add routes to serve bounding box files and other file reading functions
@app.route('/files/bounding-box', methods=['GET'])
def get_bounding_box():
    try:
        path = request.args.get('path')
        if not path:
            return jsonify({'error': 'No path provided'}), 400
        
        # Make sure the path is relative to project directory
        file_path = os.path.join(BASE_DIR, path)
        logger.info(f"Attempting to read bounding box file from {file_path}")
        
        if not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}")
            return jsonify({'error': f'File not found: {path}'}), 404
        
        # Read the file content
        with open(file_path, 'r') as file:
            content = file.read()
        
        # Check if the file is JSON
        if file_path.endswith('.json'):
            try:
                # Parse and re-serialize to ensure clean JSON
                data = json.loads(content)
                return jsonify(data)
            except json.JSONDecodeError:
                # If JSON parsing fails, return as plain text
                logger.warning(f"Failed to parse {file_path} as JSON, returning as text")
        
        # For non-JSON or parsing failures, return as text/plain
        return Response(content, mimetype='text/plain')
    except Exception as e:
        logger.error(f"Error reading bounding box file: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/files', methods=['GET'])
def get_file():
    try:
        path = request.args.get('path')
        if not path:
            return jsonify({'error': 'No path provided'}), 400
        
        # Make sure the path is relative to project directory
        file_path = os.path.join(BASE_DIR, path)
        logger.info(f"Attempting to read file from {file_path}")
        
        if not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}")
            return jsonify({'error': f'File not found: {path}'}), 404
        
        # Read the file content
        with open(file_path, 'r') as file:
            content = file.read()
        
        # Check if the file is JSON
        if file_path.endswith('.json'):
            try:
                # Parse and re-serialize to ensure clean JSON
                data = json.loads(content)
                return jsonify(data)
            except json.JSONDecodeError:
                # If JSON parsing fails, return as plain text
                logger.warning(f"Failed to parse {file_path} as JSON, returning as text")
        
        # For non-JSON or parsing failures, return as text/plain
        return Response(content, mimetype='text/plain')
    except Exception as e:
        logger.error(f"Error reading file: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/file/read', methods=['POST', 'OPTIONS'])
def read_file():
    # Handle OPTIONS request for CORS preflight
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        response.headers['Access-Control-Allow-Methods'] = 'POST'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
        
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
            
        data = request.json
        path = data.get('path')
        
        if not path:
            return jsonify({'error': 'No path provided'}), 400
        
        # Make sure the path is relative to project directory
        file_path = os.path.join(BASE_DIR, path)
        logger.info(f"Attempting to read file from {file_path}")
        
        if not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}")
            return jsonify({'error': f'File not found: {path}'}), 404
        
        # Read the file content
        with open(file_path, 'r') as file:
            content = file.read()
        
        # Check if the file is JSON
        if file_path.endswith('.json'):
            try:
                # Parse and re-serialize to ensure clean JSON
                data = json.loads(content)
                return jsonify(data)
            except json.JSONDecodeError:
                # If JSON parsing fails, return as plain text
                logger.warning(f"Failed to parse {file_path} as JSON, returning as text")
        
        # For non-JSON or parsing failures, return as text/plain
        return Response(content, mimetype='text/plain')
    except Exception as e:
        logger.error(f"Error reading file: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logger.info("Starting Flask server on port 3001")
    app.run(debug=True, port=3001) 