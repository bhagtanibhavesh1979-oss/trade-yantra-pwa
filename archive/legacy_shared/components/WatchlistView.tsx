import React, { useState } from 'react';
import { StockData } from '../types';
import { Trash2, TrendingUp, TrendingDown, Plus, Search } from 'lucide-react';
import Input from './Input';
import Button from './Button';

interface WatchlistViewProps {
  stocks: StockData[];
  onAddStock: (symbol: string) => Promise<void>;
  onRemoveStock: (token: string) => void;
}

const WatchlistView: React.FC<WatchlistViewProps> = ({ stocks, onAddStock, onRemoveStock }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [isAdding, setIsAdding] = useState(false);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchTerm) return;
    setIsAdding(true);
    await onAddStock(searchTerm);
    setSearchTerm('');
    setIsAdding(false);
  };

  return (
    <div className="max-w-5xl mx-auto py-6 px-4">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
          Market Watch
          <span className="text-sm font-normal text-slate-500 bg-slate-200 dark:bg-slate-700 px-2 py-0.5 rounded-full">
            {stocks.length}
          </span>
        </h2>
        
        <form onSubmit={handleAdd} className="flex gap-2 w-full sm:w-auto">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
            <Input 
              placeholder="Add Symbol (e.g. TATAMOTORS)" 
              className="pl-9 w-full sm:w-64"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={isAdding || !searchTerm}>
            {isAdding ? 'Adding...' : <Plus size={20} />}
          </Button>
        </form>
      </div>

      <div className="bg-white dark:bg-surface rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-700">
                <th className="p-4 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Symbol</th>
                <th className="p-4 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 text-right">Price</th>
                <th className="p-4 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 text-right">Change</th>
                <th className="p-4 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 text-right hidden sm:table-cell">W. Close</th>
                <th className="p-4 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
              {stocks.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-slate-500">
                    Your watchlist is empty. Add a stock to get started.
                  </td>
                </tr>
              ) : (
                stocks.map((stock) => {
                  const isPositive = stock.change >= 0;
                  const ColorIcon = isPositive ? TrendingUp : TrendingDown;
                  const priceColor = isPositive ? 'text-success' : 'text-danger';
                  
                  return (
                    <tr key={stock.token} className="hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors">
                      <td className="p-4">
                        <div className="font-bold text-slate-900 dark:text-white">{stock.symbol}</div>
                        <div className="text-xs text-slate-500 font-mono">{stock.token}</div>
                      </td>
                      <td className="p-4 text-right">
                        <div className={`font-mono font-bold text-lg ${priceColor} flex items-center justify-end gap-1`}>
                           {stock.ltp.toFixed(2)}
                        </div>
                      </td>
                      <td className="p-4 text-right">
                         <div className={`text-sm font-medium ${priceColor}`}>
                            {isPositive ? '+' : ''}{stock.change.toFixed(2)} ({stock.percentChange.toFixed(2)}%)
                         </div>
                      </td>
                      <td className="p-4 text-right hidden sm:table-cell text-slate-600 dark:text-slate-300 font-mono">
                        {stock.weeklyClose.toFixed(2)}
                      </td>
                      <td className="p-4 text-right">
                        <button 
                          onClick={() => onRemoveStock(stock.token)}
                          className="p-2 text-slate-400 hover:text-danger hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                        >
                          <Trash2 size={16} />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default WatchlistView;