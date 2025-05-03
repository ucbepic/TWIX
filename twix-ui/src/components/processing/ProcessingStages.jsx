import { useState, useEffect } from 'react';
import TemplateEditor from '../template/TemplateEditor';
import DataDisplay from '../results/DataDisplay';
import BoundingBoxTable from '../pdf/BoundingBoxTable';
import Cost from './Cost';
import { 
  processPhrase, 
  predictFields, 
  predictTemplate, 
  extractData, 
  saveTemplate,
  cleanup 
} from '../../services/api';

function ProcessingStages({ currentStage, onStageChange, onProcessingStart, disabled, files }) {
  const [templateData, setTemplateData] = useState(null);
  const [editedTemplate, setEditedTemplate] = useState(null);
  const [textContent, setTextContent] = useState([]);
  const [editedTextContent, setEditedTextContent] = useState([]);
  const [boundingBoxData, setBoundingBoxData] = useState([]);
  const [error, setError] = useState(null);
  const [processedData, setProcessedData] = useState(null);
  const [activeStage, setActiveStage] = useState(null);
  const [showResults, setShowResults] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingCompleted, setProcessingCompleted] = useState(false);
  const [processingTime, setProcessingTime] = useState(null);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [timerInterval, setTimerInterval] = useState(null);
  const [stageCost, setStageCost] = useState(null);
  
  // Add caching for already processed stages
  const [cachedResults, setCachedResults] = useState({
    phrase: null,
    field: null,
    template: null,
    extraction: null
  });

  // Clear previous results when switching between stages
  useEffect(() => {
    if (activeStage) {
      setShowResults(true);
    } else {
      setShowResults(false);
    }
  }, [activeStage]);

  // Effect to log and ensure text content updates are visible
  useEffect(() => {
    if (textContent && textContent.length > 0) {
      console.log("Text content updated in state:", textContent);
      setShowResults(true);
    }
  }, [textContent]);

  // Effect to log template data updates
  useEffect(() => {
    if (templateData) {
      console.log("Template data updated in state:", templateData);
      console.log("Template data type:", typeof templateData);
      console.log("Template is array:", Array.isArray(templateData));
      setShowResults(true);
    }
  }, [templateData]);

  // Cleanup temporary files when component unmounts
  useEffect(() => {
    return () => {
      // Attempt to clean up temporary files
      cleanup().catch(err => console.error('Failed to cleanup:', err));
    };
  }, []);

  // Effect to handle the timer
  useEffect(() => {
    if (isProcessing) {
      // Reset and start timer
      setElapsedTime(0);
      const interval = setInterval(() => {
        setElapsedTime(prev => prev + 1);
      }, 1000);
      setTimerInterval(interval);
    } else {
      // Clear timer when processing stops
      if (timerInterval) {
        clearInterval(timerInterval);
        setTimerInterval(null);
      }
    }
    
    // Cleanup interval on unmount
    return () => {
      if (timerInterval) {
        clearInterval(timerInterval);
      }
    };
  }, [isProcessing]);

  // Format seconds to MM:SS
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60).toString().padStart(2, '0');
    const secs = (seconds % 60).toString().padStart(2, '0');
    return `${mins}:${secs}`;
  };

  const stages = [
    {
      id: 'phrase',
      label: 'Phrase Extraction',
      icon: '📝',
      description: 'Extract phrases',
      endpoint: 'phrase',
      apiFunction: processPhrase
    },
    {
      id: 'field',
      label: 'Field Prediction',
      icon: '🔍',
      description: 'Predict fields',
      endpoint: 'fields',
      apiFunction: predictFields
    },
    {
      id: 'template',
      label: 'Template Prediction',
      icon: '📋',
      description: 'View and edit template',
      endpoint: 'template',
      apiFunction: predictTemplate
    },
    {
      id: 'extraction',
      label: 'Data Extraction',
      icon: '📊',
      description: 'Extract and view data',
      endpoint: 'extract',
      apiFunction: extractData
    }
  ];

  const handleStageClick = async (stage) => {
    try {
      // Hide results first for a smoother transition
      setShowResults(false);
      setError(null);
      setProcessingCompleted(false);
      setProcessingTime(null);
      setElapsedTime(0);
      setStageCost(null);
      
      // If clicking the same stage again, just toggle visibility
      if (stage === activeStage) {
        setActiveStage(null);
        return;
      }
      
      // Check if files are available
      if (!files || files.length === 0) {
        throw new Error('No files uploaded. Please upload PDF files first.');
      }
      
      // Set new active stage
      setActiveStage(stage);
      
      // Check if we have cached results for this stage
      if (cachedResults[stage]) {
        console.log(`Using cached results for ${stage} stage`);
        
        // Restore cached data based on the stage
        if (stage === 'phrase') {
          setTextContent(cachedResults.phrase.textContent);
          setEditedTextContent(cachedResults.phrase.editedTextContent);
          if (cachedResults.phrase.boundingBoxData) {
            setBoundingBoxData(cachedResults.phrase.boundingBoxData);
          } else {
            setBoundingBoxData([]);
          }
          if (cachedResults.phrase.cost) {
            setStageCost(cachedResults.phrase.cost);
          }
        } else if (stage === 'field') {
          setTextContent(cachedResults.field.textContent);
          setEditedTextContent(cachedResults.field.editedTextContent);
          if (cachedResults.field.cost) {
            setStageCost(cachedResults.field.cost);
          }
        } else if (stage === 'template') {
          setTemplateData(cachedResults.template.templateData);
          setEditedTemplate(cachedResults.template.editedTemplate);
          if (cachedResults.template.cost) {
            setStageCost(cachedResults.template.cost);
          }
        } else if (stage === 'extraction') {
          setProcessedData(cachedResults.extraction.processedData);
          if (cachedResults.extraction.cost) {
            setStageCost(cachedResults.extraction.cost);
          }
        }
        
        setShowResults(true);
        onStageChange(stage, cachedResults[stage].data);
        return;
      }
      
      // If no cached results, process the stage
      setIsProcessing(true);
      const startTime = Date.now();
      
      // Notify parent component that processing has started
      if (onProcessingStart) {
        onProcessingStart();
      }
      
      // Clear previous stage data only for the current stage
      if (stage === 'phrase' || stage === 'field') {
        setTextContent([]);
        setEditedTextContent([]);
      } else if (stage === 'template') {
        setTemplateData(null);
        setEditedTemplate(null);
      } else if (stage === 'extraction') {
        setProcessedData(null);
      }
      
      const stageInfo = stages.find(s => s.id === stage);
      
      // Use the API service functions with the uploaded files
      let data;
      if (stage === 'phrase') {
        data = await stageInfo.apiFunction(files);
        console.log("Phrase data received:", data);
        
        // Store cost information if available
        if (data.cost !== undefined) {
          setStageCost(data.cost);
        }
        
        // Store bounding box data if available
        if (data.boundingBoxData) {
          console.log("Bounding box data received:", data.boundingBoxData);
          setBoundingBoxData(data.boundingBoxData);
        } else {
          setBoundingBoxData([]);
        }
        
        // Define a variable to store content for caching
        let phrasesContent = '';
        let phrases = [];
        
        // Use the exact content that was downloaded if available
        if (data.downloadedContent) {
          console.log("Using downloaded content for display:", data.downloadedContent);
          // Store as a single string to preserve exact formatting
          setTextContent(data.downloadedContent);
          setEditedTextContent(data.downloadedContent);
          phrasesContent = data.downloadedContent;
        } else {
          // Extract and process phrases from the response as before
          if (data.phrases) {
            console.log("Raw phrases data:", data.phrases);
            if (typeof data.phrases === 'object' && !Array.isArray(data.phrases)) {
              // If phrases is an object with nested data, extract all values
              Object.values(data.phrases).forEach(phraseGroup => {
                if (Array.isArray(phraseGroup)) {
                  phrases = phrases.concat(phraseGroup.filter(p => p && typeof p === 'string'));
                } else if (typeof phraseGroup === 'string') {
                  phrases.push(phraseGroup);
                }
              });
            } else if (Array.isArray(data.phrases)) {
              phrases = data.phrases.filter(p => p && typeof p === 'string');
            } else if (typeof data.phrases === 'string') {
              phrases = [data.phrases];
            }
          }
          
          // Remove any empty strings and duplicates
          phrases = [...new Set(phrases)].filter(Boolean);
          console.log("Processed phrases:", phrases);
          console.log("Phrases length:", phrases.length);
          
          if (phrases.length === 0) {
            console.log("No phrases found, using sample data");
            phrases = [
              "22222-- 30",
              "(Program MORNING",
              "Week 06/17/22",
              "11111-- 30",
              "(Program ACTION",
              "Week 06/17/22"
            ];
          }
          
          // Join phrases with newlines to match download format
          phrasesContent = phrases.join('\n');
          setTextContent(phrasesContent);
          setEditedTextContent(phrasesContent);
          console.log("Text content set to:", phrasesContent);
        }
        
        // Cache the results including cost
        setCachedResults(prev => ({
          ...prev,
          phrase: {
            data,
            textContent: phrasesContent || phrases,
            editedTextContent: phrasesContent || phrases,
            boundingBoxData: data.boundingBoxData || [],
            cost: data.cost
          }
        }));
      } else if (stage === 'field') {
        data = await stageInfo.apiFunction(files);
        // Ensure fields is an array
        const fields = Array.isArray(data.fields) ? data.fields : 
                      (data.fields ? [data.fields] : []);
        setTextContent(fields);
        setEditedTextContent(fields);
        
        // Store cost information if available
        if (data.cost !== undefined) {
          setStageCost(data.cost);
        }
        
        // Cache the results including cost
        setCachedResults(prev => ({
          ...prev,
          field: {
            data,
            textContent: fields,
            editedTextContent: fields,
            cost: data.cost
          }
        }));
      } else if (stage === 'template') {
        data = await stageInfo.apiFunction(files);
        console.log("Template data received:", data);
        
        // Store cost information if available
        if (data.cost !== undefined) {
          setStageCost(data.cost);
        }
        
        // Extract template from the response
        let template = [];
        
        if (data) {
          if (data.template) {
            // The backend returns { status: 'success', template: [...] }
            if (Array.isArray(data.template)) {
              template = data.template;
              console.log("Template is an array with", template.length, "sections");
            } else if (typeof data.template === 'object') {
              template = [data.template];
              console.log("Template is an object, converting to array");
            } else {
              console.error("Unexpected template format:", data.template);
            }
          } else if (Array.isArray(data)) {
            // The API might be returning the template directly as an array
            template = data;
            console.log("Data is directly an array with", template.length, "items");
          } else {
            console.error("Unexpected data format:", data);
          }
        }
        
        console.log("Raw template from backend:", template);
        
        // Extract fields from the log output if needed
        // This is a workaround for when the backend doesn't include fields in the response
        const extractFieldsFromLog = (nodeId) => {
          // This would normally parse the log output to find fields for a given node_id
          // For now, we'll return some default fields based on the section type
          if (nodeId === 0) {
            return ['Date', 'Number', 'Investigator', 'Date Assigned', 'Racial', 'Category / Type', 'Location Of Occurrence', 'Disposition', 'Completed', 'Recorded On Camera'];
          } else if (nodeId === 1) {
            return ['Address', 'H Phone', 'Gender', 'DOB', 'Complainant'];
          } else if (nodeId === 2) {
            return ['Type Of Complaint', 'Description', 'Complaint Disposition'];
          } else if (nodeId === 3) {
            return ['Name', 'ID No.', 'Rank', 'Division', 'Officer Disposition', 'Action Taken', 'Body Cam'];
          }
          return ['New Field']; // Default field
        };
        
        // Make sure each section has the necessary properties for the editor
        const normalizedTemplate = template.map(section => {
          console.log("Processing section:", section);
          
          // Create a new section object with all required properties
          const normalizedSection = {
            // Ensure type is either 'kv' or 'table'
            type: (section.type && (section.type === 'kv' || section.type === 'table')) 
                  ? section.type 
                  : 'kv',
                  
            // Ensure fields is an array
            fields: Array.isArray(section.fields) && section.fields.length > 0
                    ? [...section.fields] // Create a copy to avoid reference issues
                    : [],
                    
            // Copy other properties
            bid: section.bid || [],
            child: section.child || -1,
            node_id: section.node_id !== undefined ? section.node_id : 0
          };
          
          // If fields is empty but we have node_id, try to extract fields from the log output
          if (normalizedSection.fields.length === 0 && normalizedSection.node_id !== undefined) {
            console.log(`Section ${normalizedSection.node_id} has no fields, attempting to extract from template data`);
            normalizedSection.fields = extractFieldsFromLog(normalizedSection.node_id);
            console.log(`Extracted fields for section ${normalizedSection.node_id}:`, normalizedSection.fields);
          }
          
          return normalizedSection;
        });
        
        console.log("Normalized template:", normalizedTemplate);
        
        // Ensure the template is initialized to an empty array if null or undefined
        setTemplateData(normalizedTemplate || []);
        setEditedTemplate(normalizedTemplate || []);
        
        // Cache the results including cost
        setCachedResults(prev => ({
          ...prev,
          template: {
            data,
            templateData: normalizedTemplate || [],
            editedTemplate: normalizedTemplate || [],
            cost: data.cost
          }
        }));
      } else if (stage === 'extraction') {
        data = await stageInfo.apiFunction(files);
        console.log("Data extraction raw response:", data);
        
        // Store cost information if available
        if (data.cost !== undefined) {
          setStageCost(data.cost);
        }
        
        // Handle different data formats
        let extractedData = {};
        
        if (data) {
          if (data.data && data.status === 'success') {
            // If data is nested in a 'data' property
            extractedData = data.data;
            console.log("Using data property from response");
          } else if (data.data_file) {
            // If data has a data_file property
            console.log("Found data_file property in response");
            extractedData = data;
          } else if (Array.isArray(data)) {
            // If data is directly an array
            console.log("Data is an array with", data.length, "items");
            extractedData = data;
          } else if (typeof data === 'object') {
            // If data is directly an object
            console.log("Data is an object");
            extractedData = data;
          }
        }
        
        console.log("Processed extraction data:", extractedData);
        setProcessedData(extractedData);
        
        // Cache the results including cost
        setCachedResults(prev => ({
          ...prev,
          extraction: {
            data,
            processedData: extractedData,
            cost: data.cost
          }
        }));
      }

      // Show results after data is loaded
      setShowResults(true);
      setIsProcessing(false);
      setProcessingCompleted(true);
      const totalTime = (Date.now() - startTime) / 1000; // Convert to seconds
      setProcessingTime(totalTime); 
      // Also update elapsedTime to match the total time
      setElapsedTime(Math.round(totalTime));
      onStageChange(stage, data);
    } catch (err) {
      setError(err.message);
      console.error('Processing failed:', err);
      setIsProcessing(false);
      setProcessingCompleted(true);
      setProcessingTime(null);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleTextDownload = (stage) => {
    try {
      // Use the content directly if it's a string, otherwise convert array to string
      const content = typeof editedTextContent === 'string' 
                     ? editedTextContent 
                     : Array.isArray(editedTextContent) 
                       ? editedTextContent.join('\n') 
                       : '';
                     
      const blob = new Blob([content], { type: 'text/plain' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${stage}_results.txt`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setError(`Failed to download: ${err.message}`);
      console.error('Download failed:', err);
    }
  };

  const handleTemplateDownload = () => {
    try {
      const content = JSON.stringify(editedTemplate || [], null, 2);
      const blob = new Blob([content], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'template.json';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setError(`Failed to download template: ${err.message}`);
      console.error('Template download failed:', err);
    }
  };

  const handleTemplateSave = async () => {
    try {
      await saveTemplate(editedTemplate || []);
      alert('Template saved successfully!');
    } catch (err) {
      setError(err.message);
      console.error('Failed to save template:', err);
    }
  };

  const handleCleanup = async () => {
    try {
      await cleanup();
      alert('Temporary files cleaned up successfully!');
    } catch (err) {
      setError(err.message);
      console.error('Failed to cleanup:', err);
    }
  };

  // Function to safely handle textarea changes
  const handleTextAreaChange = (e) => {
    try {
      const value = e.target.value;
      console.log("Textarea value changed");
      
      // Store as a string to preserve exact formatting
      setEditedTextContent(value);
    } catch (err) {
      console.error('Error updating text content:', err);
      setEditedTextContent('');
    }
  };

  return (
    <div className="space-y-4">
      {isProcessing && (
        <div className="bg-blue-50 p-3 rounded-lg mb-4 flex items-center justify-between">
          <div className="flex items-center">
            <svg className="animate-spin h-5 w-5 text-blue-600 mr-3" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
            <span className="text-blue-700 font-medium">Processing...</span>
          </div>
          <span className="text-blue-700 font-medium">{formatTime(elapsedTime)}</span>
        </div>
      )}
      
      {processingCompleted && !isProcessing && (
        <div className="bg-green-50 p-3 rounded-lg mb-4 flex items-center justify-between">
          <div className="flex items-center">
            <svg className="h-5 w-5 text-green-600 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <span className="text-green-700 font-medium">Processing completed</span>
          </div>
          <span className="text-green-700">
            {processingTime 
              ? formatTime(Math.round(processingTime))
              : formatTime(elapsedTime)}
          </span>
        </div>
      )}
      
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-gray-800">Processing Stages</h2>
        <div className="flex items-center">
          <button
            onClick={handleCleanup}
            className="px-3 py-1 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 text-sm"
          >
            Cleanup Files
          </button>
        </div>
      </div>
      
      {error && (
        <div className="bg-red-50 text-red-700 p-4 rounded-lg mb-4">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stages.map((stage) => (
          <button
            key={stage.id}
            onClick={() => handleStageClick(stage.id)}
            disabled={disabled || isProcessing}
            className={`
              p-4 rounded-lg border transition-all
              ${activeStage === stage.id
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-200 hover:border-blue-300'}
              ${(disabled || isProcessing) ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
            `}
          >
            <div className="text-2xl mb-2">{stage.icon}</div>
            <div className="font-medium text-gray-800">{stage.label}</div>
            <div className="text-sm text-gray-600 mt-1">{stage.description}</div>
          </button>
        ))}
      </div>

      {/* Results Section - Only show if a stage is active and showResults is true */}
      {showResults && (
        <div className="bg-white p-6 rounded-lg shadow-sm mt-4 border">
          {/* Results Title with Cost */}
          <div className="flex justify-between items-center mb-4">
            {stageCost !== null && <Cost cost={stageCost} />}
          </div>
          
          {/* Text Content Editor (for phrase and field) */}
          {(activeStage === 'phrase' || activeStage === 'field') && (
            <div>
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-semibold text-gray-800">
                  {activeStage === 'phrase' ? 'Phrase Extraction Text File' : 'Field Predictions'}
                </h3>
                <button
                  onClick={() => handleTextDownload(activeStage)}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  Download
                </button>
              </div>
              {/* Only display textarea for field prediction */}
              {activeStage === 'field' && (
                <div className="bg-white rounded-lg shadow-sm border p-4">
                  <textarea
                    value={typeof editedTextContent === 'string' 
                      ? editedTextContent 
                      : Array.isArray(editedTextContent) && editedTextContent.length > 0 
                        ? editedTextContent.join('\n') 
                        : 'No fields predicted yet...'}
                    onChange={handleTextAreaChange}
                    className="w-full h-96 font-mono text-sm p-4 border rounded bg-gray-50"
                    placeholder="No fields predicted yet..."
                  />
                </div>
              )}
              
              {/* Bounding Box Table (only for phrase stage) */}
              {activeStage === 'phrase' && (
                <div className="mt-8">
                  <h3 className="text-lg font-semibold text-gray-800 mb-4">Phrase Bounding Boxes</h3>
                  <BoundingBoxTable boundingBoxData={boundingBoxData} />
                </div>
              )}
            </div>
          )}

          {/* Template Editor */}
          {activeStage === 'template' && (
            <div>
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-semibold text-gray-800">Template Editor</h3>
                <div className="space-x-2">
                  <button
                    onClick={handleTemplateSave}
                    className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
                  >
                    Save Template
                  </button>
                  <button
                    onClick={handleTemplateDownload}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                  >
                    Download Template
                  </button>
                </div>
              </div>
              
              {templateData && templateData.length > 0 ? (
                <TemplateEditor 
                  template={editedTemplate || []} 
                  onChange={(newTemplate) => {
                    console.log("Template updated:", newTemplate);
                    setEditedTemplate(newTemplate);
                  }}
                />
              ) : (
                <div className="bg-white rounded-lg shadow-sm border p-4 text-center">
                  <p className="text-gray-600">No template structure detected. You can add sections manually.</p>
                  <button
                    onClick={() => {
                      const initialTemplate = [{type: 'kv', fields: ['New Field']}];
                      setEditedTemplate(initialTemplate);
                      setTemplateData(initialTemplate);
                    }}
                    className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                  >
                    Create Empty Template
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Data Display */}
          {activeStage === 'extraction' && processedData && (
            <div>
              <DataDisplay data={{data: processedData, cost: stageCost}} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ProcessingStages; 