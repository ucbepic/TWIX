import { useState, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';

// Set up PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js`;

function PDFViewer({ file }) {
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [url, setUrl] = useState(null);
  const [scale, setScale] = useState(1.2);
  const [rotation, setRotation] = useState(0);

  useEffect(() => {
    if (file) {
      const fileUrl = URL.createObjectURL(file);
      setUrl(fileUrl);
      return () => URL.revokeObjectURL(fileUrl);
    }
  }, [file]);

  function onDocumentLoadSuccess({ numPages }) {
    setNumPages(numPages);
    setPageNumber(1);
  }

  const rotate = (delta) => {
    setRotation((prev) => (prev + delta + 360) % 360);
  };

  return (
    <div className="flex flex-col h-full bg-gray-100 rounded-lg">
      {url ? (
        <>
          <div className="bg-white border-b px-4 py-2 flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setPageNumber(p => Math.max(1, p - 1))}
                  disabled={pageNumber <= 1}
                  className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-50"
                  title="Previous Page"
                >
                  ←
                </button>
                <span className="text-sm">
                  Page {pageNumber} of {numPages || '--'}
                </span>
                <button
                  onClick={() => setPageNumber(p => Math.min(numPages || p, p + 1))}
                  disabled={pageNumber >= (numPages || pageNumber)}
                  className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-50"
                  title="Next Page"
                >
                  →
                </button>
              </div>

              <div className="flex items-center space-x-2 border-l pl-4">
                <button
                  onClick={() => setScale(s => Math.max(0.5, s - 0.1))}
                  className="p-2 rounded-lg hover:bg-gray-100"
                  title="Zoom Out"
                >
                  -
                </button>
                <span className="text-sm w-16 text-center">
                  {Math.round(scale * 100)}%
                </span>
                <button
                  onClick={() => setScale(s => Math.min(2.5, s + 0.1))}
                  className="p-2 rounded-lg hover:bg-gray-100"
                  title="Zoom In"
                >
                  +
                </button>
              </div>

              <div className="flex items-center space-x-2 border-l pl-4">
                <button
                  onClick={() => rotate(-90)}
                  className="p-2 rounded-lg hover:bg-gray-100"
                  title="Rotate Left"
                >
                  ↺
                </button>
                <button
                  onClick={() => rotate(90)}
                  className="p-2 rounded-lg hover:bg-gray-100"
                  title="Rotate Right"
                >
                  ↻
                </button>
              </div>
            </div>

            <div className="text-sm text-gray-600 truncate max-w-md">
              {file.name}
            </div>
          </div>

          <div className="flex-1 overflow-auto p-4">
            <div className="flex justify-center">
              <Document
                file={url}
                onLoadSuccess={onDocumentLoadSuccess}
                className="shadow-2xl"
              >
                <Page
                  pageNumber={pageNumber}
                  scale={scale}
                  rotate={rotation}
                  className="bg-white"
                  renderAnnotationLayer={false}
                  renderTextLayer={false}
                />
              </Document>
            </div>
          </div>
        </>
      ) : (
        <div className="h-full flex items-center justify-center text-gray-500">
          <div className="text-center">
            <div className="text-4xl mb-2">📄</div>
            <p>Select a PDF to preview</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default PDFViewer; 