import { StockData } from '../types';

// Helper to generate consistent mock data
const createStock = (token: string, symbol: string, price: number): StockData => {
  return {
    token,
    symbol,
    ltp: price,
    change: 0,
    percentChange: 0,
    weeklyClose: Math.round(price * 0.98 * 10) / 10, // Simulate slightly lower weekly close for demo
    color: 'white'
  };
};

const INITIAL_STOCKS: StockData[] = [
  // Nifty 50 & Major F&O Stocks
  createStock('2885', 'RELIANCE', 2450.50),
  createStock('11536', 'TCS', 3500.00),
  createStock('1333', 'HDFCBANK', 1650.00),
  createStock('10940', 'INFY', 1420.00),
  createStock('4963', 'ICICIBANK', 950.25),
  createStock('1394', 'HUL', 2550.00),
  createStock('1660', 'ITC', 445.50),
  createStock('3045', 'SBIN', 580.20),
  createStock('10604', 'BHARTIARTL', 820.00),
  createStock('317', 'BAJFINANCE', 7200.00),
  createStock('1922', 'KOTAKBANK', 1850.00),
  createStock('11483', 'LT', 2350.00),
  createStock('7229', 'HCLTECH', 1150.00),
  createStock('5900', 'AXISBANK', 960.00),
  createStock('236', 'ASIANPAINT', 3100.00),
  createStock('10999', 'MARUTI', 9500.00),
  createStock('3351', 'SUNPHARMA', 1020.00),
  createStock('3506', 'TITAN', 2950.00),
  createStock('11532', 'ULTRACEMCO', 8200.00),
  createStock('3787', 'WIPRO', 405.00),
  createStock('2475', 'ONGC', 160.00),
  createStock('17963', 'NESTLEIND', 22000.00),
  createStock('25', 'ADANIENT', 2400.00),
  createStock('14977', 'POWERGRID', 245.00),
  createStock('3499', 'TATASTEEL', 115.00),
  createStock('11723', 'JSWSTEEL', 780.00),
  createStock('11630', 'NTPC', 190.00),
  createStock('1232', 'GRASIM', 1750.00),
  createStock('2031', 'M&M', 1550.00),
  createStock('467', 'HDFCLIFE', 620.00),
  createStock('15083', 'ADANIPORTS', 750.00),
  createStock('16669', 'BAJAJFINSV', 1500.00),
  createStock('3456', 'TATAMOTORS', 620.00),
  createStock('21808', 'SBILIFE', 1250.00),
  createStock('526', 'COALINDIA', 230.00),
  createStock('1363', 'HINDALCO', 450.00),
  createStock('526', 'BPCL', 360.00),
  createStock('881', 'DRREDDY', 5200.00),
  createStock('910', 'EICHERMOT', 3400.00),
  createStock('13538', 'TECHM', 1100.00),
  createStock('10940', 'DIVISLAB', 3600.00),
  createStock('694', 'CIPLA', 1050.00),
  createStock('547', 'BRITANNIA', 4800.00),
  createStock('3432', 'TATACONSUM', 850.00),
  createStock('1348', 'HEROMOTOCO', 2950.00),
  createStock('157', 'APOLLOHOSP', 5100.00),
  createStock('11287', 'UPL', 680.00),
  createStock('5258', 'INDUSINDBK', 1300.00),
  createStock('10940', 'HAVELLS', 1320.00),
  createStock('11536', 'PIDILITIND', 2600.00),
];

class MockAngelService {
  private subscribers: ((data: StockData[]) => void)[] = [];
  private intervalId: number | null = null;
  private currentStocks: StockData[] = [...INITIAL_STOCKS];

  connect() {
    console.log('Connecting to Mock Smart Stream...');
    if (this.intervalId) return;

    this.intervalId = window.setInterval(() => {
      this.simulateMarketMovement();
    }, 1000);
  }

  disconnect() {
    if (this.intervalId) {
      window.clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }

  subscribe(callback: (data: StockData[]) => void) {
    this.subscribers.push(callback);
    // Send immediate initial data
    callback(this.currentStocks);
    return () => {
      this.subscribers = this.subscribers.filter(cb => cb !== callback);
    };
  }

  private simulateMarketMovement() {
    // Randomly update prices to simulate live feed
    this.currentStocks = this.currentStocks.map(stock => {
      const volatility = stock.ltp * 0.0005; // 0.05% volatility
      const change = (Math.random() - 0.5) * volatility;
      const newLtp = Number((stock.ltp + change).toFixed(2));
      
      const newColor = newLtp > stock.ltp ? 'green' : (newLtp < stock.ltp ? 'red' : stock.color);

      return {
        ...stock,
        ltp: newLtp,
        change: Number((stock.change + change).toFixed(2)),
        percentChange: Number(((stock.change + change) / (stock.ltp - stock.change) * 100).toFixed(2)),
        color: newColor
      };
    });

    this.notifySubscribers();
  }

  private notifySubscribers() {
    this.subscribers.forEach(cb => cb(this.currentStocks));
  }

  getStocks() {
    return this.currentStocks;
  }
  
  // Simulate adding a token (in reality this would fetch from master json)
  async addToken(symbolOrToken: string): Promise<StockData | null> {
    await new Promise(r => setTimeout(r, 500)); // Network delay
    
    // Check if already exists
    const exists = this.currentStocks.find(s => s.symbol === symbolOrToken.toUpperCase() || s.token === symbolOrToken);
    if (exists) return exists;

    // Create a mock new stock
    const basePrice = Math.floor(Math.random() * 2000) + 100;
    const newStock: StockData = {
      token: Math.floor(Math.random() * 100000).toString(),
      symbol: symbolOrToken.toUpperCase(),
      ltp: basePrice,
      change: 0,
      percentChange: 0,
      weeklyClose: basePrice * 0.95,
      color: 'white'
    };
    
    this.currentStocks.push(newStock);
    this.notifySubscribers();
    return newStock;
  }

  removeToken(token: string) {
    this.currentStocks = this.currentStocks.filter(s => s.token !== token);
    this.notifySubscribers();
  }
}

export const angelService = new MockAngelService();