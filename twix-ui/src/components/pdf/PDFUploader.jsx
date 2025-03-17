import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';

function PDFUploader({ onUpload, disabled }) {
  const onDrop = useCallback((acceptedFiles) => {
    const pdfFiles = acceptedFiles.filter(
      file => file.type === 'application/pdf'
    );
    onUpload(pdfFiles);
  }, [onUpload]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf']
    },
    disabled
  });

  return (
    <div
      {...getRootProps()}
      className={`
        border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
        transition-colors duration-200
        ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300'}
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'hover:border-blue-500'}
      `}
    >
      <input {...getInputProps()} />
      <div className="space-y-2">
        <div className="text-4xl">📄</div>
        <p className="text-lg text-gray-700">
          {isDragActive
            ? "Drop your PDF files here"
            : "Drag & drop PDF files here, or click to select"}
        </p>
        <p className="text-sm text-gray-500">
          You can upload multiple PDF files at once
        </p>
      </div>
    </div>
  );
}

export default PDFUploader; 