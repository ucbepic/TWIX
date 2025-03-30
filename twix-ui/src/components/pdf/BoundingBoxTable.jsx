import React from 'react';

function BoundingBoxTable({ boundingBoxData }) {
  // Check if we have valid bounding box data
  if (!boundingBoxData || !Array.isArray(boundingBoxData) || boundingBoxData.length === 0) {
    return (
      <div className="bg-yellow-50 border border-yellow-100 text-yellow-700 p-4 rounded-md mb-4">
        <p>No bounding box data available. The file may not have been generated yet.</p>
      </div>
    );
  }

  // Extract header from the first row or use default headers if needed
  const headers = boundingBoxData[0] || ['text', 'x0', 'y0', 'x1', 'y1', 'page'];
  
  // Display rows excluding the header
  const rows = boundingBoxData.slice(1);

  // Format numeric values to make them more readable
  const formatValue = (value, index) => {
    // Text column (first column)
    if (index === 0) {
      // Remove any surrounding quotes (from CSV parsing)
      const cleanText = value ? String(value).replace(/^"|"$/g, '') : '';
      return cleanText || '(empty)';
    }
    
    // For numeric columns (coordinates and page), format as numbers with 2 decimal places
    if (value !== undefined && value !== null && value !== '') {
      const num = parseFloat(value);
      if (!isNaN(num)) {
        return num.toFixed(2);
      }
    }
    
    // If the value is undefined, null, or not a number, return a meaningful default
    return index === 5 ? '1' : '0.00'; // Default to page 1 or coordinate 0.00
  };

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200 border rounded-lg">
        <thead className="bg-gray-50">
          <tr>
            {headers.map((header, index) => (
              <th 
                key={index} 
                className={`px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider ${
                  index === 0 ? 'text-left' : 'text-center'
                }`}
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} className={rowIndex % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
              {row.map((cell, cellIndex) => (
                <td 
                  key={cellIndex} 
                  className={`px-6 py-4 text-sm text-gray-500 ${
                    cellIndex === 0 
                      ? 'max-w-xs truncate whitespace-normal break-words' 
                      : 'whitespace-nowrap text-center font-mono'
                  }`}
                  title={cellIndex === 0 ? String(cell || '') : undefined}
                >
                  {formatValue(cell, cellIndex)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-2 text-sm text-gray-600">
        Total: {rows.length} phrases
      </div>
    </div>
  );
}

export default BoundingBoxTable; 