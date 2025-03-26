import { useState, useEffect } from 'react';

function TemplateEditor({ template = [], onChange }) {
  const [expandedSections, setExpandedSections] = useState([]);
  
  // Validate template when it changes
  useEffect(() => {
    // If template isn't valid, initialize it
    if (!template || !Array.isArray(template) || template.length === 0) {
      console.log("Template is invalid, initializing with empty array");
      onChange([]);
    } else {
      console.log("Template is valid with", template.length, "sections");
    }
  }, [template]);

  // Auto-expand all sections when template changes and has items
  useEffect(() => {
    if (template && Array.isArray(template) && template.length > 0) {
      // Create an array of all section indices to expand them all
      const allSections = Array.from({ length: template.length }, (_, i) => i);
      setExpandedSections(allSections);
      console.log("Auto-expanding all sections");
    }
  }, [template]);

  // Log expanded sections for debugging
  useEffect(() => {
    if (expandedSections.length > 0 && template && Array.isArray(template)) {
      console.log(`Expanded sections:`, expandedSections);
      expandedSections.forEach(sectionIndex => {
        if (template[sectionIndex]) {
          console.log(`Fields for section ${sectionIndex}:`, template[sectionIndex].fields);
        }
      });
    }
  }, [expandedSections, template]);

  const handleFieldChange = (sectionIndex, fieldIndex, value) => {
    if (!template || !Array.isArray(template)) return;
    
    const newTemplate = [...template];
    if (!newTemplate[sectionIndex] || !newTemplate[sectionIndex].fields) {
      return;
    }
    
    newTemplate[sectionIndex].fields[fieldIndex] = value;
    onChange(newTemplate);
  };

  const addSection = (insertIndex = template.length) => {
    if (!template || !Array.isArray(template)) {
      const newTemplate = [{ type: 'kv', fields: ['New Field'] }];
      onChange(newTemplate);
      setExpandedSections([0]);
      return;
    }
    
    const newTemplate = [...template];
    newTemplate.splice(insertIndex, 0, {
      type: 'kv', // Changed default type from 'text' to 'kv'
      fields: ['New Field'] // Default field
    });
    onChange(newTemplate);
    
    // Add the new section to expanded sections
    setExpandedSections(prev => [...prev, insertIndex].sort((a, b) => a - b));
  };

  const deleteSection = (sectionIndex) => {
    if (!template || !Array.isArray(template) || template.length === 0) return;
    
    const newTemplate = template.filter((_, index) => index !== sectionIndex);
    onChange(newTemplate);
    
    // Remove the deleted section from expanded sections and adjust indices
    setExpandedSections(prev => 
      prev.filter(i => i !== sectionIndex)
         .map(i => i > sectionIndex ? i - 1 : i)
    );
  };

  const addField = (sectionIndex) => {
    if (!template || !Array.isArray(template) || !template[sectionIndex]) return;
    
    const newTemplate = [...template];
    if (!newTemplate[sectionIndex].fields) {
      newTemplate[sectionIndex].fields = [];
    }
    newTemplate[sectionIndex].fields.push('New Field');
    onChange(newTemplate);
  };

  const deleteField = (sectionIndex, fieldIndex) => {
    if (!template || !Array.isArray(template) || 
        !template[sectionIndex] || !template[sectionIndex].fields) return;
    
    const newTemplate = [...template];
    newTemplate[sectionIndex].fields = newTemplate[sectionIndex].fields.filter((_, index) => index !== fieldIndex);
    onChange(newTemplate);
  };

  const toggleSectionType = (sectionIndex) => {
    if (!template || !Array.isArray(template) || !template[sectionIndex]) return;
    
    const newTemplate = [...template];
    // Toggle between 'table' and 'kv' instead of 'table' and 'text'
    newTemplate[sectionIndex].type = newTemplate[sectionIndex].type === 'table' ? 'kv' : 'table';
    onChange(newTemplate);
  };

  const toggleSectionExpansion = (sectionIndex) => {
    setExpandedSections(prev => {
      // If section is already expanded, remove it from the array
      if (prev.includes(sectionIndex)) {
        return prev.filter(i => i !== sectionIndex);
      }
      // Otherwise add it to the array and sort
      return [...prev, sectionIndex].sort((a, b) => a - b);
    });
  };

  const expandAllSections = () => {
    const allSections = Array.from({ length: template.length }, (_, i) => i);
    setExpandedSections(allSections);
  };

  const collapseAllSections = () => {
    setExpandedSections([]);
  };

  return (
    <div className="space-y-2">
      {/* Controls for all sections */}
      <div className="flex justify-end mb-4 gap-2">
        <button 
          className="text-blue-600 hover:text-blue-800 bg-blue-50 px-3 py-1 rounded hover:bg-blue-100"
          onClick={expandAllSections}
        >
          Expand All
        </button>
        <button 
          className="text-blue-600 hover:text-blue-800 bg-blue-50 px-3 py-1 rounded hover:bg-blue-100"
          onClick={collapseAllSections}
        >
          Collapse All
        </button>
      </div>

      {/* Insert button at the top */}
      <div 
        className="border-2 border-dashed border-gray-300 rounded-lg p-2 flex items-center justify-center cursor-pointer hover:bg-gray-100"
        onClick={() => addSection(0)}
      >
        <span className="text-gray-500">+ Insert Section</span>
      </div>

      {template.map((section, sectionIndex) => (
        <div key={sectionIndex}>
          <div className="border rounded-lg bg-white shadow-sm">
            <div 
              className={`p-4 flex items-center justify-between hover:bg-gray-50 ${
                expandedSections.includes(sectionIndex) ? 'border-b' : ''
              }`}
            >
              <div className="flex items-center gap-4">
                <span 
                  className="text-lg font-medium cursor-pointer"
                  onClick={() => toggleSectionExpansion(sectionIndex)}
                >
                  {section.type === 'table' ? '📋' : '🔑'} Section {sectionIndex + 1}
                </span>
                <button 
                  className="text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded hover:bg-gray-200"
                  onClick={() => toggleSectionType(sectionIndex)}
                >
                  {section.type}
                </button>
              </div>
              <div className="flex gap-2">
                <button 
                  className="text-blue-600 hover:text-blue-800"
                  onClick={() => toggleSectionExpansion(sectionIndex)}
                >
                  {expandedSections.includes(sectionIndex) ? 'Collapse' : 'Expand'}
                </button>
                <button 
                  className="text-red-600 hover:text-red-800 ml-4"
                  onClick={() => deleteSection(sectionIndex)}
                >
                  Delete
                </button>
              </div>
            </div>

            {expandedSections.includes(sectionIndex) && (
              <div className="p-4 bg-gray-50">
                {/* Show message if no fields */}
                {(!section.fields || section.fields.length === 0) && (
                  <div className="text-center text-gray-500 mb-4">
                    No fields found for this section. Add fields below.
                  </div>
                )}
                
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {/* Ensure fields is always treated as an array */}
                  {(Array.isArray(section.fields) ? section.fields : []).map((field, fieldIndex) => (
                    <div
                      key={fieldIndex}
                      className="bg-white rounded-lg p-4 shadow-sm border border-gray-200 relative"
                    >
                      <input
                        type="text"
                        value={field || ''}
                        onChange={(e) => handleFieldChange(sectionIndex, fieldIndex, e.target.value)}
                        className="w-full bg-transparent focus:outline-none focus:ring-2 focus:ring-blue-500 rounded px-2 py-1"
                        placeholder="Field name"
                      />
                      <button
                        className="absolute top-2 right-2 text-red-500 hover:text-red-700"
                        onClick={() => deleteField(sectionIndex, fieldIndex)}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                  <div 
                    className="border-2 border-dashed border-gray-300 rounded-lg p-4 flex items-center justify-center cursor-pointer hover:bg-gray-100"
                    onClick={() => addField(sectionIndex)}
                  >
                    <span className="text-gray-500">+ Add Field</span>
                  </div>
                </div>
              </div>
            )}
          </div>
          
          {/* Insert button between sections */}
          <div 
            className="border-2 border-dashed border-gray-300 rounded-lg p-2 flex items-center justify-center cursor-pointer hover:bg-gray-100 my-2"
            onClick={() => addSection(sectionIndex + 1)}
          >
            <span className="text-gray-500">+ Insert Section</span>
          </div>
        </div>
      ))}
      
      {/* Final add button if there are no sections yet */}
      {template.length === 0 && (
        <div 
          className="border-2 border-dashed border-gray-300 rounded-lg p-4 flex items-center justify-center cursor-pointer hover:bg-gray-100"
          onClick={() => addSection()}
        >
          <span className="text-gray-500">+ Add Section</span>
        </div>
      )}
    </div>
  );
}

export default TemplateEditor;