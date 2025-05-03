import React from 'react';

const Cost = ({ cost }) => {
  
  return (
    <div className="inline-flex items-center px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm font-medium">
      <span className="mr-1">Cumulative Cost:</span>
      <span className="font-bold">${typeof cost === 'number' ? cost.toFixed(4) : cost}</span>
    </div>
  );
};

export default Cost; 