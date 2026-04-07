export interface StockData {
  token: string;
  symbol: string;
  ltp: number; // Last Traded Price
  change: number;
  percentChange: number;
  weeklyClose: number; // For the auto-alert feature
  color: 'green' | 'red' | 'white';
}

export enum AlertCondition {
  ABOVE = 'ABOVE',
  BELOW = 'BELOW'
}

export interface Alert {
  id: string;
  token: string;
  symbol: string;
  condition: AlertCondition;
  price: number;
  active: boolean;
  createdAt: Date;
  type: 'MANUAL' | 'AUTO';
}

export interface AlertLog {
  id: string;
  symbol: string;
  message: string;
  timestamp: Date;
  price: number;
  type: 'TRIGGERED' | 'INFO';
}

export interface UserSession {
  clientId: string;
  isAuthenticated: boolean;
}

export type ViewState = 'AUTH' | 'WATCHLIST' | 'ALERTS';
