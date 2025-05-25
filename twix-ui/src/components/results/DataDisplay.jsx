import { useState, useEffect } from 'react';
import { stringifyOrderedJSON, createOrderPreservingReplacer } from '../../services/api';
import Cost from '../processing/Cost';

const DataDisplay = ({ data, cost }) => {
  const [processedData, setProcessedData] = useState([]);
  const [expandedDetails, setExpandedDetails] = useState({});
  const [originalOrder, setOriginalOrder] = useState({});
  
  useEffect(() => {
    if (!data) {
      setProcessedData([]);
      return;
    }
    
    try {
      console.log("Raw data received:", data);
      
      // Extract actual data from object if necessary
      let actualData = data;
      if (data.data) {
        actualData = data.data;
      }
      
      // Parse string data
      let processedJson = actualData;
      if (typeof actualData === 'string') {
        try {
          processedJson = JSON.parse(actualData);
          console.log("Parsed string data into:", processedJson);
        } catch (e) {
          console.error("Failed to parse data string:", e);
        }
      }
      
      // Normalize the data to the expected format of array of records with id and content
      let normalizedData = [];
      
      // Store original attribute order for each record
      const orderMap = {};
      
      // Process function to capture field order for tables
      const captureTableFieldOrder = (item, itemIdx, recordIdx) => {
        if (item && item.type === 'table' && item.content && Array.isArray(item.content) && item.content.length > 0) {
          const itemKey = `record_${recordIdx}_item_${itemIdx}`;
          // Get keys from first object - critically preserving their exact original order
          const firstRow = item.content[0];
          if (firstRow && typeof firstRow === 'object') {
            // We need to preserve the exact order from the original object
            const keys = Object.keys(firstRow);
            orderMap[itemKey] = keys;
            console.log(`Captured field order for ${itemKey}:`, keys);
          }
        }
      };

      // Helper function to recursively find and extract all array data that follows our expected format
      const extractDataArrays = (obj, depth = 0) => {
        // Base case: if we hit a null or primitive value, return empty array
        if (obj === null || typeof obj !== 'object') {
          return [];
        }
        
        // First, let's check if this object itself follows our expected format with id and content
        if (Array.isArray(obj) && obj.length > 0 && obj.some(item => 'id' in item && 'content' in item)) {
          // Check if the content contains items with type: "table" or type: "kv"
          const hasTypeContentStructure = obj.some(item => 
            item.content && Array.isArray(item.content) && 
            item.content.some(contentItem => 
              contentItem && typeof contentItem === 'object' && 
              (contentItem.type === 'table' || contentItem.type === 'kv')
            )
          );
          
          if (hasTypeContentStructure) {
            return obj;
          }
        }
        
        // Check if this is an array of objects with type and content (tables and key-value pairs)
        if (Array.isArray(obj) && obj.length > 0 && 
            obj.some(item => 'type' in item && 'content' in item) &&
            obj.some(item => item.type === 'table' || item.type === 'kv')) {
          return [{ id: 0, content: obj }];
        }
        
        // Recursive case: check all properties (if object) or elements (if array)
        let results = [];
        
        if (Array.isArray(obj)) {
          // For arrays, search each element
          for (let i = 0; i < obj.length; i++) {
            const found = extractDataArrays(obj[i], depth + 1);
            if (found.length > 0) {
              results = results.concat(found);
            }
          }
        } else {
          // For objects, search each property
          for (const key in obj) {
            const found = extractDataArrays(obj[key], depth + 1);
            if (found.length > 0) {
              results = results.concat(found);
            }
          }
        }
        
        return results;
      };
      
      // Start search from the processed JSON
      const extractedArrays = extractDataArrays(processedJson);
      
      if (extractedArrays.length > 0) {
        console.log("Found extractable data arrays:", extractedArrays);
        normalizedData = extractedArrays;
        
        // Track original attribute order for the items we found
        normalizedData.forEach((record, recordIdx) => {
          if (record.content && Array.isArray(record.content)) {
            record.content.forEach((item, itemIdx) => {
              captureTableFieldOrder(item, itemIdx, recordIdx);
              
              // Also handle key-value pairs
              if (item && item.type === 'kv' && item.content) {
                const itemKey = `record_${recordIdx}_item_${itemIdx}`;
                if (Array.isArray(item.content)) {
                  // For array of kv objects, store original order
                  const keys = item.content.map(kv => Object.keys(kv)[0]);
                  orderMap[itemKey] = keys;
                } else if (typeof item.content === 'object') {
                  // For single kv object, store key order
                  orderMap[itemKey] = Object.keys(item.content);
                }
              }
            });
          }
        });
      }
      // Case 1: If data is already an array of records with id and content (old code kept for backward compatibility)
      else if (Array.isArray(processedJson) && 
          processedJson.length > 0 && 
          processedJson.some(item => 'id' in item && 'content' in item)) {
        console.log("Data is already in the expected records format");
        normalizedData = processedJson;
        
        // Track original attribute order for each content item
        processedJson.forEach((record, recordIdx) => {
          if (record.content && Array.isArray(record.content)) {
            record.content.forEach((item, itemIdx) => {
              captureTableFieldOrder(item, itemIdx, recordIdx);
              
              // Also handle key-value pairs
              if (item && item.type === 'kv' && item.content) {
                const itemKey = `record_${recordIdx}_item_${itemIdx}`;
                if (Array.isArray(item.content)) {
                  // For array of kv objects, store original order
                  const keys = item.content.map(kv => Object.keys(kv)[0]);
                  orderMap[itemKey] = keys;
                } else if (typeof item.content === 'object') {
                  // For single kv object, store key order
                  orderMap[itemKey] = Object.keys(item.content);
                }
              }
            });
          }
        });
      }
      // Case 2: If data is an array of objects with type and content (tables and key-value pairs)
      else if (Array.isArray(processedJson) && 
              processedJson.length > 0 && 
              processedJson.some(item => 'type' in item && 'content' in item)) {
        console.log("Data is an array of type-content objects, wrapping in a record");
        normalizedData = [{ id: 0, content: processedJson }];
        
        // Track original attribute order
        processedJson.forEach((item, itemIdx) => {
          captureTableFieldOrder(item, itemIdx, 0);
          
          // Also handle key-value pairs
          if (item && item.type === 'kv' && item.content) {
            const itemKey = `record_0_item_${itemIdx}`;
            if (Array.isArray(item.content)) {
              // For array of kv objects, store original order
              const keys = item.content.map(kv => Object.keys(kv)[0]);
              orderMap[itemKey] = keys;
            } else if (typeof item.content === 'object') {
              // For single kv object, store key order
              orderMap[itemKey] = Object.keys(item.content);
            }
          }
        });
      }
      // Case 3: If data has a data_file property that's an array
      else if (processedJson && processedJson.data_file && Array.isArray(processedJson.data_file)) {
        console.log("Found data_file array, using it");
        if (processedJson.data_file.some(item => 'id' in item && 'content' in item)) {
          normalizedData = processedJson.data_file;
          
          // Track original attribute order
          processedJson.data_file.forEach((record, recordIdx) => {
            if (record.content && Array.isArray(record.content)) {
              record.content.forEach((item, itemIdx) => {
                captureTableFieldOrder(item, itemIdx, recordIdx);
                
                // Also handle key-value pairs
                if (item && item.type === 'kv' && item.content) {
                  const itemKey = `record_${recordIdx}_item_${itemIdx}`;
                  if (Array.isArray(item.content)) {
                    // For array of kv objects, store original order
                    const keys = item.content.map(kv => Object.keys(kv)[0]);
                    orderMap[itemKey] = keys;
                  } else if (typeof item.content === 'object') {
                    // For single kv object, store key order
                    orderMap[itemKey] = Object.keys(item.content);
                  }
                }
              });
            }
          });
        } else if (processedJson.data_file.some(item => 'type' in item && 'content' in item)) {
          normalizedData = [{ id: 0, content: processedJson.data_file }];
          
          // Track original attribute order
          processedJson.data_file.forEach((item, itemIdx) => {
            captureTableFieldOrder(item, itemIdx, 0);
            
            // Also handle key-value pairs
            if (item && item.type === 'kv' && item.content) {
              const itemKey = `record_0_item_${itemIdx}`;
              if (Array.isArray(item.content)) {
                // For array of kv objects, store original order
                const keys = item.content.map(kv => Object.keys(kv)[0]);
                orderMap[itemKey] = keys;
              } else if (typeof item.content === 'object') {
                // For single kv object, store key order
                orderMap[itemKey] = Object.keys(item.content);
              }
            }
          });
        }
      }
      // Case 4: If data has a Investigations_Redacted_modified property that's an array
      else if (processedJson && processedJson.Investigations_Redacted_modified && Array.isArray(processedJson.Investigations_Redacted_modified)) {
        console.log("Found Investigations_Redacted_modified array, using it");
        
        // Map the data to the expected format - creating records with id and content
        normalizedData = processedJson.Investigations_Redacted_modified.map((item, index) => {
          // Extract content if it exists, otherwise use the whole item
          const content = item.content || [item];
          return {
            id: index,
            content: Array.isArray(content) ? content : [content]
          };
        });
        
        // Track original attribute order
        processedJson.Investigations_Redacted_modified.forEach((item, recordIdx) => {
          if (item.content && Array.isArray(item.content)) {
            item.content.forEach((contentItem, itemIdx) => {
              captureTableFieldOrder(contentItem, itemIdx, recordIdx);
              
              // Also handle key-value pairs
              if (contentItem && contentItem.type === 'kv' && contentItem.content) {
                const itemKey = `record_${recordIdx}_item_${itemIdx}`;
                if (Array.isArray(contentItem.content)) {
                  const keys = contentItem.content.map(kv => Object.keys(kv)[0]);
                  orderMap[itemKey] = keys;
                } else if (typeof contentItem.content === 'object') {
                  orderMap[itemKey] = Object.keys(contentItem.content);
                }
              }
            });
          }
        });
      }
      
      console.log("Normalized data:", normalizedData);
      console.log("Original attribute order:", orderMap);
      setProcessedData(normalizedData);
      setOriginalOrder(orderMap);
      
      // Initialize expanded state for all View Details sections
      const initialExpandedState = {};
      normalizedData.forEach((record, recordIndex) => {
        initialExpandedState[`record_${recordIndex}`] = false;
        if (record.content) {
          record.content.forEach((item, itemIndex) => {
            initialExpandedState[`section_${recordIndex}_${itemIndex}`] = false;
          });
        }
      });
      setExpandedDetails(initialExpandedState);
      
    } catch (error) {
      console.error("Error processing data:", error);
      setProcessedData([]);
    }
  }, [data]);

  const toggleDetails = (key) => {
    setExpandedDetails(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  const renderValue = (value) => {
    if (value === null || value === undefined || value === 'missing') {
      return <span className="text-gray-400 italic">missing</span>;
    }
    
    if (value === 'N/A') {
      return <span className="text-gray-400">N/A</span>;
    }
    
    if (value === 'Not Stated') {
      return <span className="text-gray-500">Not Stated</span>;
    }
    
    if (typeof value === 'object') {
      return (
        <details className="cursor-pointer">
          <summary className="text-blue-600 hover:text-blue-800">View Details</summary>
          <pre className="mt-2 text-xs bg-gray-100 p-2 rounded overflow-auto max-h-60">
            {JSON.stringify(value, null, 2)}
          </pre>
        </details>
      );
    }
    
    // Check for cid pattern - strings with "(cid:xx)" format
    if (typeof value === 'string' && value.includes('(cid:')) {
      return <span className="text-gray-500">{value}</span>;
    }
    
    // Check if it's a URL
    if (typeof value === 'string' && value.match(/^https?:\/\//i)) {
      return (
        <a 
          href={value} 
          target="_blank" 
          rel="noopener noreferrer" 
          className="text-blue-600 hover:text-blue-800 hover:underline"
        >
          {value}
        </a>
      );
    }
    
    // Default rendering
    return String(value);
  };

  const renderTable = (tableData, tableIndex, recordIndex) => {
    if (!Array.isArray(tableData) || tableData.length === 0) {
      return <p className="text-gray-500 italic">No table data available</p>;
    }

    // Get original column order or extract all unique keys
    const itemKey = `record_${recordIndex}_item_${tableIndex}`;
    console.log(`Rendering table ${itemKey}, stored order:`, originalOrder[itemKey]);
    let headers = originalOrder[itemKey] || [];
    
    // If no stored order, try to preserve the order from the first row
    if (!headers.length && tableData.length > 0 && typeof tableData[0] === 'object') {
      // Use the keys from the first object in their original order
      headers = Object.keys(tableData[0]);
      console.log(`No stored order found, using keys from first row:`, headers);
    }
    
    // If still no headers (possibly because first row was empty), extract all unique keys
    if (!headers.length) {
      const allKeys = new Set();
      tableData.forEach(row => {
        if (row && typeof row === 'object') {
          Object.keys(row).forEach(key => allKeys.add(key));
        }
      });
      headers = Array.from(allKeys);
      console.log(`Extracted keys from all rows:`, headers);
    }
    
    return (
      <div className="overflow-x-auto border rounded-lg shadow-sm bg-white">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
              {headers.map((header, index) => (
                  <th
                  key={`header-${index}`}
                  scope="col" 
                  className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                  >
                  {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
            {tableData.map((row, rowIndex) => {
              // Ensure we use the original object to preserve property order
              const orderedRow = {};
              headers.forEach(header => {
                orderedRow[header] = row[header];
              });
              
              return (
                <tr key={`row-${rowIndex}`} className="hover:bg-gray-50">
                  {headers.map((header, cellIndex) => (
                    <td key={`cell-${rowIndex}-${cellIndex}`} className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                      {row[header] !== undefined ? renderValue(row[header]) : <span className="text-gray-400 italic">missing</span>}
                    </td>
                  ))}
                </tr>
              );
            })}
            </tbody>
          </table>
      </div>
    );
  };

  const renderKeyValuePairs = (data, itemIndex, recordIndex) => {
    if (!data || (Array.isArray(data) && data.length === 0) || (typeof data === 'object' && Object.keys(data).length === 0)) {
      return <p className="text-gray-500 italic">No key-value data available</p>;
    }

    // Get original key order if available
    const itemKey = `record_${recordIndex}_item_${itemIndex}`;
    const orderedKeys = originalOrder[itemKey] || [];
    
    // If data is an array of objects with single key-value pairs, process accordingly
    let keyValuePairs = [];
    
    if (Array.isArray(data)) {
      data.forEach(item => {
        if (typeof item === 'object' && item !== null) {
          const keys = Object.keys(item);
          if (keys.length === 1) {
            keyValuePairs.push({ 
              key: keys[0], 
              value: item[keys[0]] 
            });
          }
        }
      });
    } else if (typeof data === 'object') {
      // Use original order if available, otherwise use object keys
      if (orderedKeys.length > 0) {
        keyValuePairs = orderedKeys.map(key => ({
          key,
          value: data[key]
        }));
      } else {
        keyValuePairs = Object.entries(data).map(([key, value]) => ({ key, value }));
      }
    }

    return (
      <div className="bg-white border rounded-lg shadow-sm p-4">
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2">
          {keyValuePairs.map((pair, index) => (
            <div key={`kv-${index}`} className="py-2 border-b">
              <dt className="text-sm font-medium text-gray-500">{pair.key}</dt>
              <dd className="mt-1 text-sm text-gray-900 break-words">
                {renderValue(pair.value)}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    );
  };

  const renderContent = (content, recordIndex) => {
    return content.map((item, itemIndex) => {
      if (!item || typeof item !== 'object' || !('type' in item) || !('content' in item)) {
        return (
          <div key={`invalid-content-${recordIndex}-${itemIndex}`} className="p-4 border border-yellow-300 bg-yellow-50 rounded-md mb-4">
            <p className="text-yellow-700">Invalid content format</p>
            <pre className="mt-2 text-xs bg-gray-100 p-2 rounded overflow-auto max-h-20">
              {typeof item === 'object' ? JSON.stringify(item, null, 2) : String(item)}
            </pre>
          </div>
        );
      }
      
      const sectionKey = `section_${recordIndex}_${itemIndex}`;
      const isExpanded = expandedDetails[sectionKey] || false;
      
      return (
        <div key={`content-${recordIndex}-${itemIndex}`} className="mb-6">
          <div className="bg-white border rounded-lg shadow-sm overflow-hidden">
            <div className="bg-gray-50 px-4 py-3 border-b flex justify-between items-center">
              <h4 className="font-medium text-gray-700">
                {item.type === 'table' ? 'Table Data' : 'Key-Value Data'}
              </h4>
              <button 
                onClick={() => toggleDetails(sectionKey)}
                className="text-blue-600 hover:text-blue-800 text-sm flex items-center"
              >
                {isExpanded ? 'Hide Details' : 'View Details'}
                <svg className={`ml-1 h-4 w-4 transform ${isExpanded ? 'rotate-180' : ''}`} fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                </svg>
              </button>
            </div>
            <div className={`transition-all duration-300 ${isExpanded ? 'opacity-100 block' : 'opacity-0 hidden'}`}>
              <div className="p-3 bg-gray-100">
                <pre className="whitespace-pre-wrap text-xs overflow-auto max-h-60">
                  {JSON.stringify(item.content, null, 2)}
                </pre>
              </div>
            </div>
            <div className="p-4">
              {item.type === 'table' 
                ? renderTable(item.content, itemIndex, recordIndex) 
                : renderKeyValuePairs(item.content, itemIndex, recordIndex)}
            </div>
          </div>
        </div>
      );
    });
  };

  const handleDownload = () => {
    try {
      // Ensure we have data to download
      if (!processedData || processedData.length === 0) {
        console.error("No data to download");
        return;
      }
      
      // Extract and format the data for download
      const dataToDownload = processedData.map(record => {
        return record.content;
      });
      
      // Create a JSON blob with the downloaded data
      const blob = new Blob([JSON.stringify(dataToDownload, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      
      // Create and trigger download link
      const a = document.createElement('a');
      a.href = url;
      a.download = 'extracted_data.json';
      document.body.appendChild(a);
      a.click();
      
      // Cleanup
      URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (e) {
      console.error("Failed to download data:", e);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl font-bold">Extracted Data</h2>
        <div className="flex items-center space-x-4">
          <button
            onClick={handleDownload}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 flex items-center"
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Download JSON
          </button>
        </div>
      </div>

      {(() => {
        const totalRecords = processedData.length;
        const displayCount = Math.min(20, totalRecords);
        const limitedData = processedData.slice(0, 20);

        return (
          <>
            <p className="text-sm text-gray-600 mb-4">
              Showing {displayCount} of {totalRecords} extracted objects
            </p>

            {limitedData.map((record, recordIndex) => {
              if (!record || typeof record !== 'object' || !('content' in record)) {
                return (
                  <div key={`invalid-record-${recordIndex}`} className="p-4 border border-yellow-300 bg-yellow-50 rounded-md mb-4">
                    <p className="text-yellow-700">Invalid record format at index {recordIndex}</p>
                    <pre className="mt-2 text-xs bg-gray-100 p-2 rounded overflow-auto max-h-20">
                      {typeof record === 'object' ? JSON.stringify(record, null, 2) : String(record)}
                    </pre>
                  </div>
                );
              }

              const recordKey = `record_${recordIndex}`;
              const isExpanded = expandedDetails[recordKey] || false;

              return (
                <div key={`record-${recordIndex}`} className="mb-10 pb-6 border-b border-gray-200">
                  <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-semibold text-gray-800">
                      Record: {record.id !== undefined ? record.id : recordIndex}
                    </h3>
                    <button
                      onClick={() => toggleDetails(recordKey)}
                      className="text-blue-600 hover:text-blue-800 text-sm flex items-center"
                    >
                      {isExpanded ? 'Hide Details' : 'View Details'}
                      <svg className={`ml-1 h-4 w-4 transform ${isExpanded ? 'rotate-180' : ''}`} fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                      </svg>
                    </button>
                  </div>

                  <div className={`transition-all duration-300 mb-6 ${isExpanded ? 'opacity-100 block' : 'opacity-0 hidden'}`}>
                    <div className="bg-gray-100 rounded p-3">
                      <pre className="whitespace-pre-wrap text-xs overflow-auto max-h-60">
                        {JSON.stringify(record, null, 2)}
                      </pre>
                    </div>
                  </div>

                  {Array.isArray(record.content) ? (
                    renderContent(record.content, recordIndex)
                  ) : (
                    <div className="p-4 border border-yellow-300 bg-yellow-50 rounded-md mb-4">
                      <p className="text-yellow-700">Content is not an array</p>
                      <pre className="mt-2 text-xs bg-gray-100 p-2 rounded overflow-auto max-h-20">
                        {typeof record.content === 'object' ? JSON.stringify(record.content, null, 2) : String(record.content)}
                      </pre>
                    </div>
                  )}
                </div>
              );
            })}
          </>
        );
      })()}
    </div>
  );
};

export default DataDisplay;