import React from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

const Input: React.FC<InputProps> = ({ label, error, className = '', ...props }) => {
  return (
    <div className="flex flex-col gap-1 w-full">
      {label && (
        <label className="text-sm font-medium text-slate-600 dark:text-slate-300">
          {label}
        </label>
      )}
      <input
        className={`px-3 py-2 bg-white dark:bg-surface border border-slate-300 dark:border-slate-600 rounded-lg 
        text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary 
        disabled:bg-slate-100 dark:disabled:bg-slate-800 ${error ? 'border-danger' : ''} ${className}`}
        {...props}
      />
      {error && <span className="text-xs text-danger">{error}</span>}
    </div>
  );
};

export default Input;