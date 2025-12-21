import React from 'react';
import { ViewState } from '../types';
import { Sun, Moon, LogOut, BarChart2, Bell, Lock, TrendingUp } from 'lucide-react';

interface NavbarProps {
  currentView: ViewState;
  setView: (view: ViewState) => void;
  isAuthenticated: boolean;
  onLogout: () => void;
  isDark: boolean;
  toggleTheme: () => void;
}

const Navbar: React.FC<NavbarProps> = ({ 
  currentView, 
  setView, 
  isAuthenticated, 
  onLogout,
  isDark,
  toggleTheme
}) => {
  return (
    <nav className="sticky top-0 z-50 w-full bg-white dark:bg-surface border-b border-slate-200 dark:border-slate-700 px-4 py-3 shadow-sm">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="bg-gradient-to-br from-primary to-indigo-600 p-2 rounded-lg shadow-lg shadow-primary/20">
            <TrendingUp className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-xl font-bold hidden sm:block text-slate-900 dark:text-white tracking-tight">
            Trade <span className="text-primary">Yantra</span>
          </h1>
        </div>

        <div className="flex items-center gap-2">
           {isAuthenticated && (
            <div className="flex bg-slate-100 dark:bg-slate-900 rounded-lg p-1 mr-2">
               <button
                onClick={() => setView('WATCHLIST')}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors flex items-center gap-2
                  ${currentView === 'WATCHLIST' 
                    ? 'bg-white dark:bg-slate-700 text-primary shadow-sm' 
                    : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'}`}
              >
                <BarChart2 size={16} />
                <span className="hidden sm:inline">Watchlist</span>
              </button>
              <button
                onClick={() => setView('ALERTS')}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors flex items-center gap-2
                  ${currentView === 'ALERTS' 
                    ? 'bg-white dark:bg-slate-700 text-primary shadow-sm' 
                    : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'}`}
              >
                <Bell size={16} />
                <span className="hidden sm:inline">Alerts</span>
              </button>
            </div>
           )}

          <button 
            onClick={toggleTheme}
            className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-500 dark:text-slate-400 transition-colors"
          >
            {isDark ? <Sun size={20} /> : <Moon size={20} />}
          </button>

          {isAuthenticated ? (
            <button 
              onClick={onLogout}
              className="p-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-danger transition-colors"
              title="Logout"
            >
              <LogOut size={20} />
            </button>
          ) : (
            <div className="flex items-center gap-1 text-xs text-slate-500 font-mono bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded">
               <Lock size={12} /> Secure
            </div>
          )}
        </div>
      </div>
    </nav>
  );
};

export default Navbar;