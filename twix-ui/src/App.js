import { useState } from 'react';
import Navbar from './components/layout/Navbar';
import Footer from './components/layout/Footer';
import PDFUploader from './components/pdf/PDFUploader';
import PDFList from './components/pdf/PDFList';
import ProcessingStages from './components/processing/ProcessingStages';
import ProcessingStatus from './components/processing/ProcessingStatus';
import TwixApiTest from './components/TwixApiTest';

function App() {
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [currentStage, setCurrentStage] = useState('upload');
  const [processedData, setProcessedData] = useState(null);
  const [showApiTest, setShowApiTest] = useState(false);
  const [status, setStatus] = useState({
    isProcessing: false,
    message: '',
    error: null
  });

  const handleStageChange = (stage, data) => {
    setCurrentStage(stage);
    
    if (stage === 'extraction') {
      console.log("Extraction data in App.js:", data);
      // Handle different data formats
      if (data && data.data) {
        setProcessedData(data.data);
      } else if (data) {
        setProcessedData(data);
      } else {
        setProcessedData({});
      }
    }
    
    setStatus({
      isProcessing: false,
      message: `${stage} processing completed`,
      error: null
    });
  };

  const handleProcessingStart = () => {
    setStatus({
      isProcessing: true,
      message: 'Processing...',
      error: null
    });
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Navbar />
      
      <main className="flex-grow container mx-auto px-4 py-8">
        <div className="bg-white rounded-lg shadow-lg p-6">
          <div className="mb-8 flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-800">TWIX Project</h1>
              <p className="text-gray-600 mt-2">
                PDF Processing and Data Extraction Tool
              </p>
            </div>
            <button
              onClick={() => setShowApiTest(!showApiTest)}
              className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700"
            >
              {showApiTest ? 'Hide API Test' : 'Show API Test'}
            </button>
          </div>

          {showApiTest ? (
            <section className="mb-8">
              <TwixApiTest />
            </section>
          ) : (
            <>
              <section className="mb-8">
                <PDFUploader 
                  onUpload={setUploadedFiles}
                  disabled={status.isProcessing}
                />
              </section>

              {uploadedFiles.length > 0 && (
                <section className="mb-8">
                  <PDFList 
                    files={uploadedFiles}
                    onRemove={(index) => {
                      setUploadedFiles(files => 
                        files.filter((_, i) => i !== index)
                      );
                    }}
                  />
                </section>
              )}

              <section className="mb-8">
                <ProcessingStages
                  currentStage={currentStage}
                  onStageChange={handleStageChange}
                  onProcessingStart={handleProcessingStart}
                  disabled={status.isProcessing || !uploadedFiles.length}
                  files={uploadedFiles}
                />
              </section>

              <ProcessingStatus status={status} />
            </>
          )}
        </div>
      </main>

      <Footer />
    </div>
  );
}

export default App;
