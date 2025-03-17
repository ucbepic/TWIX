import { useState } from 'react';
import PDFViewer from './PDFViewer';

function PDFList({ files, onRemove }) {
  const [selectedFile, setSelectedFile] = useState(null);

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold text-gray-800">Uploaded Files</h2>
      
      <div className="grid md:grid-cols-3 gap-6">
        {/* File List */}
        <div className="h-[700px] bg-white rounded-lg shadow-sm border overflow-hidden">
          <div className="p-4 border-b bg-gray-50">
            <h3 className="font-medium text-gray-700">Documents</h3>
            <p className="text-sm text-gray-500 mt-1">
              {files.length} file{files.length !== 1 ? 's' : ''} uploaded
            </p>
          </div>
          <div className="p-2 space-y-2 overflow-auto h-[calc(100%-4rem)]">
            {files.map((file, index) => (
              <div
                key={`${file.name}-${index}`}
                className={`
                  flex items-center justify-between p-3 rounded-lg 
                  transition-colors cursor-pointer
                  ${selectedFile === file 
                    ? 'bg-blue-50 border border-blue-200' 
                    : 'bg-gray-50 hover:bg-gray-100 border border-transparent'
                  }
                `}
                onClick={() => setSelectedFile(file)}
              >
                <div className="flex items-center space-x-3 flex-1 min-w-0">
                  <span className="text-xl">📄</span>
                  <span className="text-sm text-gray-700 truncate">
                    {file.name}
                  </span>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onRemove(index);
                    if (selectedFile === file) {
                      setSelectedFile(null);
                    }
                  }}
                  className="ml-2 p-1 text-gray-400 hover:text-red-500 rounded-full hover:bg-red-50"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* PDF Preview */}
        <div className="md:col-span-2 h-[700px] bg-white rounded-lg shadow-sm border overflow-hidden">
          <PDFViewer file={selectedFile} />
        </div>
      </div>
    </div>
  );
}

export default PDFList; 