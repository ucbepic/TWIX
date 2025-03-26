import { useState, useEffect, useRef } from 'react';

function ProcessingStatus({ status }) {
  const [elapsedTime, setElapsedTime] = useState(0);
  const [finalTime, setFinalTime] = useState(null);
  const timerRef = useRef(null);
  
  useEffect(() => {
    // Clear any existing timer when status changes
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    
    if (status.isProcessing) {
      // Reset timer when processing starts
      setElapsedTime(0);
      
      // Set up timer to update every second
      timerRef.current = setInterval(() => {
        setElapsedTime(prev => prev + 1);
      }, 1000);
    } else if (elapsedTime > 0) {
      // When processing stops, save the final time
      setFinalTime(elapsedTime);
    }
    
    return () => {
      // Clean up timer when component unmounts
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [status.isProcessing]); // Removed elapsedTime from dependencies
  
  // Format seconds into MM:SS
  const formatTime = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

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
          <span>Processing... {formatTime(elapsedTime)}</span>
        </div>
      )}
      {!status.isProcessing && status.message && (
        <div className="flex items-center">
          <p>{status.message}</p>
          {finalTime > 0 && (
            <span className="ml-2 text-sm bg-blue-100 px-2 py-1 rounded">
              Time: {formatTime(finalTime)}
            </span>
          )}
        </div>
      )}
      {status.error && <p className="text-red-600">{status.error}</p>}
    </div>
  );
}

export default ProcessingStatus; 