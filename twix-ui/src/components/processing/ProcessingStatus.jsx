function ProcessingStatus({ status }) {
  if (!status.isProcessing && !status.message && !status.error) {
    return null;
  }

  return (
    <div className={`
      p-4 rounded-lg
      ${status.error ? 'bg-red-50 text-red-700' : 'bg-blue-50 text-blue-700'}
    `}>
      {status.isProcessing && (
        <div className="flex items-center">
          <svg className="animate-spin h-5 w-5 mr-3" viewBox="0 0 24 24">
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
          Processing...
        </div>
      )}
      {status.message && <p>{status.message}</p>}
      {status.error && <p className="text-red-600">{status.error}</p>}
    </div>
  );
}

export default ProcessingStatus; 