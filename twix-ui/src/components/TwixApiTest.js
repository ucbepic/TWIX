import React, { useState } from 'react';
import { 
  addFields, 
  removeFields, 
  removeTemplateNode, 
  modifyTemplateNode,
  predictTemplate,
  predictFields
} from '../services/api';

const TwixApiTest = () => {
  const [fields, setFields] = useState([]);
  const [template, setTemplate] = useState([]);
  const [newField, setNewField] = useState('');
  const [removeField, setRemoveField] = useState('');
  const [nodeId, setNodeId] = useState(0);
  const [nodeType, setNodeType] = useState('kv');
  const [nodeFields, setNodeFields] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchFields = async () => {
    try {
      setLoading(true);
      const response = await predictFields([]);
      setFields(response.fields);
      setMessage('Fields fetched successfully');
    } catch (error) {
      setMessage(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchTemplate = async () => {
    try {
      setLoading(true);
      const response = await predictTemplate([]);
      setTemplate(response.template);
      setMessage('Template fetched successfully');
    } catch (error) {
      setMessage(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleAddField = async () => {
    if (!newField.trim()) {
      setMessage('Please enter a field to add');
      return;
    }

    try {
      setLoading(true);
      const response = await addFields([newField]);
      setFields(response.fields);
      setMessage(`Field "${newField}" added successfully`);
      setNewField('');
    } catch (error) {
      setMessage(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveField = async () => {
    if (!removeField.trim()) {
      setMessage('Please enter a field to remove');
      return;
    }

    try {
      setLoading(true);
      const response = await removeFields([removeField]);
      setFields(response.fields);
      setMessage(`Field "${removeField}" removed successfully`);
      setRemoveField('');
    } catch (error) {
      setMessage(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveNode = async () => {
    try {
      setLoading(true);
      const response = await removeTemplateNode([parseInt(nodeId)]);
      setTemplate(response.template);
      setMessage(`Node ${nodeId} removed successfully`);
    } catch (error) {
      setMessage(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleModifyNode = async () => {
    if (!nodeFields.trim()) {
      setMessage('Please enter fields for the node');
      return;
    }

    try {
      setLoading(true);
      const fieldsArray = nodeFields.split(',').map(field => field.trim());
      const response = await modifyTemplateNode(parseInt(nodeId), nodeType, fieldsArray);
      setTemplate(response.template);
      setMessage(`Node ${nodeId} modified successfully`);
    } catch (error) {
      setMessage(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-4 bg-white rounded shadow">
      <h2 className="text-xl font-bold mb-4">Twix API Test</h2>
      
      {message && (
        <div className="mb-4 p-2 bg-blue-100 text-blue-800 rounded">
          {message}
        </div>
      )}

      <div className="mb-6">
        <h3 className="text-lg font-semibold mb-2">Fields</h3>
        <button 
          onClick={fetchFields}
          disabled={loading}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 mr-2"
        >
          Fetch Fields
        </button>
        
        <div className="mt-2">
          <div className="flex mb-2">
            <input
              type="text"
              value={newField}
              onChange={(e) => setNewField(e.target.value)}
              placeholder="Field to add"
              className="border p-2 rounded mr-2 flex-grow"
            />
            <button 
              onClick={handleAddField}
              disabled={loading}
              className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
            >
              Add Field
            </button>
          </div>
          
          <div className="flex">
            <input
              type="text"
              value={removeField}
              onChange={(e) => setRemoveField(e.target.value)}
              placeholder="Field to remove"
              className="border p-2 rounded mr-2 flex-grow"
            />
            <button 
              onClick={handleRemoveField}
              disabled={loading}
              className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
            >
              Remove Field
            </button>
          </div>
        </div>
        
        <div className="mt-2 max-h-40 overflow-y-auto border p-2 rounded">
          <h4 className="font-medium">Current Fields:</h4>
          <ul className="list-disc pl-5">
            {fields.map((field, index) => (
              <li key={index}>{field}</li>
            ))}
          </ul>
        </div>
      </div>

      <div className="mb-6">
        <h3 className="text-lg font-semibold mb-2">Template</h3>
        <button 
          onClick={fetchTemplate}
          disabled={loading}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 mb-2"
        >
          Fetch Template
        </button>
        
        <div className="grid grid-cols-2 gap-4">
          <div>
            <h4 className="font-medium mb-2">Remove Node</h4>
            <div className="flex">
              <input
                type="number"
                value={nodeId}
                onChange={(e) => setNodeId(e.target.value)}
                placeholder="Node ID"
                className="border p-2 rounded mr-2 flex-grow"
              />
              <button 
                onClick={handleRemoveNode}
                disabled={loading}
                className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
              >
                Remove
              </button>
            </div>
          </div>
          
          <div>
            <h4 className="font-medium mb-2">Modify Node</h4>
            <div className="mb-2">
              <input
                type="number"
                value={nodeId}
                onChange={(e) => setNodeId(e.target.value)}
                placeholder="Node ID"
                className="border p-2 rounded w-full"
              />
            </div>
            <div className="mb-2">
              <select
                value={nodeType}
                onChange={(e) => setNodeType(e.target.value)}
                className="border p-2 rounded w-full"
              >
                <option value="kv">Key-Value</option>
                <option value="table">Table</option>
              </select>
            </div>
            <div className="mb-2">
              <input
                type="text"
                value={nodeFields}
                onChange={(e) => setNodeFields(e.target.value)}
                placeholder="Fields (comma separated)"
                className="border p-2 rounded w-full"
              />
            </div>
            <button 
              onClick={handleModifyNode}
              disabled={loading}
              className="px-4 py-2 bg-yellow-500 text-white rounded hover:bg-yellow-600 w-full"
            >
              Modify
            </button>
          </div>
        </div>
        
        <div className="mt-2 max-h-60 overflow-y-auto border p-2 rounded">
          <h4 className="font-medium">Current Template:</h4>
          <pre className="text-xs">{JSON.stringify(template, null, 2)}</pre>
        </div>
      </div>
    </div>
  );
};

export default TwixApiTest; 