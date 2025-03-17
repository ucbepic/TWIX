from flask import Flask, send_file, jsonify, request
from flask_cors import CORS
import json
import os
import sys
import tempfile
import shutil
import logging

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
        
        # Use twix to extract phrases
        logger.info(f"Extracting phrases from {len(pdf_paths)} PDFs")
        phrases = twix.extract_phrase(pdf_paths)
        logger.info(f"Extracted {len(phrases)} phrases")
        
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
        
        # Use twix to predict fields
        logger.info(f"Predicting fields from {len(pdf_paths)} PDFs")
        fields = twix.predict_field(pdf_paths)
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
        
        # Use twix to predict template
        logger.info(f"Predicting template from {len(pdf_paths)} PDFs")
        template = twix.predict_template(pdf_paths)
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
        
        # Use twix to extract data
        logger.info(f"Extracting data from {len(pdf_paths)} PDFs")
        data = twix.extract_data(pdf_paths)
        logger.info(f"Extracted data successfully")
        
        return jsonify({
            'status': 'success',
            'data': data
        })
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
        
        # Use twix.add_fields with the PDF paths
        updated_fields = twix.add_fields(added_fields, data_files=pdf_paths)
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
        
        # Use twix.remove_fields with the PDF paths
        updated_fields = twix.remove_fields(removed_fields, data_files=pdf_paths)
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
        
        # Use twix.remove_template_node with the PDF paths
        updated_template = twix.remove_template_node(node_ids, data_files=pdf_paths)
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
        
        # Use twix.modify_template_node with the PDF paths
        updated_template = twix.modify_template_node(node_id, node_type, fields, data_files=pdf_paths)
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

if __name__ == '__main__':
    logger.info("Starting Flask server on port 3001")
    app.run(debug=True, port=3001) 