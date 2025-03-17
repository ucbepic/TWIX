import { useState, useCallback } from 'react';
import * as api from '../services/api';

export function usePDFProcessor() {
  const [status, setStatus] = useState({
    isProcessing: false,
    message: '',
    error: null
  });

  const processStage = useCallback(async (stage, files) => {
    setStatus({
      isProcessing: true,
      message: `Processing ${stage}...`,
      error: null
    });

    try {
      let result;
      switch (stage) {
        case 'phrase':
          result = await api.processPhrase(files);
          break;
        case 'field':
          result = await api.predictFields(files);
          break;
        case 'template':
          result = await api.predictTemplate(files);
          break;
        case 'extraction':
          result = await api.extractData(files);
          break;
        default:
          throw new Error('Invalid processing stage');
      }

      setStatus({
        isProcessing: false,
        message: `${stage} processing completed successfully`,
        error: null
      });

      return result;
    } catch (error) {
      setStatus({
        isProcessing: false,
        message: '',
        error: error.message
      });
      throw error;
    }
  }, []);

  return {
    status,
    processStage
  };
} 