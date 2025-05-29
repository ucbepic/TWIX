from flask import Flask, send_file, jsonify, request, Response
from flask_cors import CORS
import json
import os
import sys
import tempfile
import shutil
from collections import OrderedDict
import twix.extract


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
        
        if not files or len(files) == 0:
            return jsonify({'error': 'No files uploaded'}), 400

        # Get visionFeature flag from the form
        vision_feature_flag = request.form.get('visionFeature', 'false').lower() == 'true'
        model_name = request.form.get('model', 'gpt-4o')
        print("Using extract.py from:", twix.extract.__file__)
        print ("Vision Feature Flag: ", vision_feature_flag)
        print ("Model Name: ", model_name)

        # Save uploaded files to temporary directory
        pdf_paths = []
        for file in files:
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(file_path)
            pdf_paths.append(file_path)

        # Create accessible directories for bounding box files
        result_folder = twix.extract.get_result_folder_path(pdf_paths)
        os.makedirs(os.path.dirname(result_folder), exist_ok=True)
        
        # Use twix to extract phrases, pass in visionFeature flag
        phrases, cost = twix.extract_phrase(pdf_paths, result_folder, LLM_model_name=model_name, vision_feature=vision_feature_flag)
        print(cost)
        
        
        # Define paths for the bounding box files
        bb_path = os.path.join(result_folder, 'merged_phrases_bounding_box_page_number.json')
        bb_txt_path = os.path.join(os.path.dirname(result_folder), 'merged_raw_phrases_bounding_box_page_number.txt')
        
        
        
        # Copy the bounding box file to additional locations for better discoverability
        try:
            source_path = bb_txt_path if os.path.exists(bb_txt_path) else bb_path
            
            for dest_dir in ['results']:
                dest_path = os.path.join(BASE_DIR, dest_dir)
                os.makedirs(dest_path, exist_ok=True)
                
                # Create both txt and json versions in each location
                txt_dest = os.path.join(dest_path, 'merged_raw_phrases_bounding_box_page_number.txt')
                json_dest = os.path.join(dest_path, 'merged_raw_phrases_bounding_box_page_number.json')
                
                if os.path.exists(source_path):
                    # Copy TXT file as-is
                    shutil.copy(source_path, txt_dest)
                    
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
                                
                    
                            else:
                                print('CSV data was empty, no JSON created')
                        except Exception as e:
                            # If conversion fails, just copy the file as-is
                            shutil.copy(source_path, json_dest)
                    
        except Exception as copy_err:
            print('Failed to copy bounding box file: ', copy_err)
        
        return jsonify({
            'status': 'success',
            'phrases': phrases,
            'cost': cost   
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/process/fields', methods=['POST'])
def predict_fields():
    try:
        # Get uploaded files
        files = request.files.getlist('pdfs')
        
        if not files or len(files) == 0:
            return jsonify({'error': 'No files uploaded'}), 400
        
        # Save uploaded files to temporary directory
        pdf_paths = []
        for file in files:
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(file_path)
            pdf_paths.append(file_path)
        
        result_folder = twix.extract.get_result_folder_path(pdf_paths)
        
        # Use twix to predict fields
        fields, cost = twix.predict_field(pdf_paths, result_folder)
        
        return jsonify({
            'status': 'success',
            'fields': fields,
            'cost': cost
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/process/template', methods=['POST'])
def predict_template():
    try:
        # Get uploaded files
        files = request.files.getlist('pdfs')
        
        if not files or len(files) == 0:
            return jsonify({'error': 'No files uploaded'}), 400
        
        # Save uploaded files to temporary directory
        pdf_paths = []
        for file in files:
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(file_path)
            pdf_paths.append(file_path)
        
        result_folder = twix.extract.get_result_folder_path(pdf_paths)
        # Use twix to predict template
        template, cost = twix.predict_template(pdf_paths, result_folder)
        
        return jsonify({
            'status': 'success',
            'template': template,
            'cost': cost
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/process/extract', methods=['POST'])
def extract_data():
    try:
        # Get uploaded files
        files = request.files.getlist('pdfs')
        
        if not files or len(files) == 0:
            return jsonify({'error': 'No files uploaded'}), 400
        
        # Save uploaded files to temporary directory
        pdf_paths = []
        for file in files:
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(file_path)
            pdf_paths.append(file_path)
        
        result_folder = twix.extract.get_result_folder_path(pdf_paths)
        

        # Use twix to extract data
        data, cost = twix.extract_data(pdf_paths, result_folder)
        
        # Log where the extracted data is being saved
        extracted_data_path = os.path.join(result_folder, 'extracted_data.json')
        
        # Ensure the results folder exists
        os.makedirs(RESULT_FOLDER, exist_ok=True)
        
        # Save a copy of the extracted data to the results folder for easier access
        try:
            result_json_path = os.path.join(RESULT_FOLDER, 'extracted_data.json')
            with open(result_json_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as save_err:
            print('Failed to save extracted data to results folder: ', save_err)
        
        
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
            'data': ordered_data,
            'cost': cost
        }
        
        # Return the response with preserved order
        return json.dumps(response, sort_keys=False), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/save/template', methods=['POST'])
def save_template():
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        template_data = request.json
        
        
        # Get the result folder for the most recent upload
        result_folder = RESULT_FOLDER
        
        # Use twix to save the template
        template_path = os.path.join(result_folder, 'template.json')
        twix.pattern.write_template(template_data, template_path)
        
        return jsonify({
            'status': 'success',
            'message': 'Template saved successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# New endpoints using twix user_apis

@app.route('/api/add_fields', methods=['POST'])
def api_add_fields():
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.json
        added_fields = data.get('fields', [])
        
        # Get the most recent PDF files processed
        pdf_paths = []
        for filename in os.listdir(UPLOAD_FOLDER):
            if filename.lower().endswith('.pdf'):
                pdf_paths.append(os.path.join(UPLOAD_FOLDER, filename))
        

        result_folder = twix.extract.get_result_folder_path(pdf_paths)
        
        # Use twix.add_fields with the PDF paths
        updated_fields = twix.add_fields(added_fields, result_folder)
        
        return jsonify({
            'status': 'success',
            'fields': updated_fields,
            'message': 'Fields added successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/remove_fields', methods=['POST'])
def api_remove_fields():
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.json
        removed_fields = data.get('fields', [])
        
        # Get the most recent PDF files processed
        pdf_paths = []
        for filename in os.listdir(UPLOAD_FOLDER):
            if filename.lower().endswith('.pdf'):
                pdf_paths.append(os.path.join(UPLOAD_FOLDER, filename))
        

        result_folder = twix.extract.get_result_folder_path(pdf_paths)
        
        # Use twix.remove_fields with the PDF paths
        updated_fields = twix.remove_fields(removed_fields, result_folder)
        
        return jsonify({
            'status': 'success',
            'fields': updated_fields,
            'message': 'Fields removed successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/remove_template_node', methods=['POST'])
def api_remove_template_node():
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.json
        node_ids = data.get('node_ids', [])
        
        # Get the most recent PDF files processed
        pdf_paths = []
        for filename in os.listdir(UPLOAD_FOLDER):
            if filename.lower().endswith('.pdf'):
                pdf_paths.append(os.path.join(UPLOAD_FOLDER, filename))
        

        result_folder = twix.extract.get_result_folder_path(pdf_paths)
        
        # Use twix.remove_template_node with the PDF paths
        updated_template = twix.remove_template_node(node_ids, result_folder)
        
        
        return jsonify({
            'status': 'success',
            'template': updated_template,
            'message': 'Template nodes removed successfully'
        })
    except Exception as e:
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
        
        
        if node_id is None or node_type is None:
            return jsonify({'error': 'node_id and type are required'}), 400
        
        # Get the most recent PDF files processed
        pdf_paths = []
        for filename in os.listdir(UPLOAD_FOLDER):
            if filename.lower().endswith('.pdf'):
                pdf_paths.append(os.path.join(UPLOAD_FOLDER, filename))
        

        result_folder = twix.extract.get_result_folder_path(pdf_paths)
        
        # Use twix.modify_template_node with the PDF paths
        updated_template = twix.modify_template_node(node_id, node_type, fields, result_folder)
        
        return jsonify({
            'status': 'success',
            'template': updated_template,
            'message': 'Template node modified successfully'
        })
    except Exception as e:
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
        
      
        
        return jsonify({
            'status': 'success',
            'message': f'Cleaned up {count} temporary files successfully'
        })
    except Exception as e:
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
        
        if not os.path.exists(file_path):
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
                print('Failed to parse {file_path} as JSON, returning as text')
        
        # For non-JSON or parsing failures, return as text/plain
        return Response(content, mimetype='text/plain')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/files', methods=['GET'])
def get_file():
    try:
        path = request.args.get('path')
        if not path:
            return jsonify({'error': 'No path provided'}), 400
        
        # Make sure the path is relative to project directory
        file_path = os.path.join(BASE_DIR, path)
        
        if not os.path.exists(file_path):
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
                print('Failed to parse {file_path} as JSON, returning as text')
        
        # For non-JSON or parsing failures, return as text/plain
        return Response(content, mimetype='text/plain')
    except Exception as e:
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
        
        if not os.path.exists(file_path):
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
                print('Failed to parse {file_path} as JSON, returning as text')
        
        # For non-JSON or parsing failures, return as text/plain
        return Response(content, mimetype='text/plain')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=3001) 