"""
Angel One API Service
Handles login, LTP fetching, historical data, and scrip master
"""
from SmartApi import SmartConnect
import pyotp
import requests
import time
import datetime
import os
import json
from typing import Optional, Dict, List, Tuple

SCRIPMASTER_FILE = "scripmaster.json"

class AngelService:
    def __init__(self):
        self.scrips = []
        self.master_loaded = False

    def login(self, api_key: str, client_id: str, password: str, totp_secret: str) -> Tuple[bool, str, Optional[SmartConnect], Optional[Dict]]:
        """
        Login to Angel One
        Returns: (success, message, smart_api, tokens_dict)
        """
        try:
            smart_api = SmartConnect(api_key=api_key)
            totp_val = pyotp.TOTP(totp_secret).now()
            data = smart_api.generateSession(client_id, password, totp_val)
            
            if data.get('status'):
                tokens = {
                    'jwt_token': data['data']['jwtToken'],
                    'feed_token': data['data']['feedToken'],
                    'refresh_token': data['data']['refreshToken']
                }
                return True, "Login Successful", smart_api, tokens
            else:
                return False, data.get('message', 'Unknown Login Error'), None, None
        except Exception as e:
            return False, str(e), None, None

    def fetch_ltp(self, smart_api: SmartConnect, symbol: str, token: str) -> Optional[float]:
        """
        Fetch Last Traded Price
        """
        try:
            ltp_data = smart_api.ltpData("NSE", symbol, token)
            if ltp_data and ltp_data.get('status'):
                return ltp_data['data']['ltp']
        except Exception as e:
            print(f"LTP fetch error for {symbol}: {e}")
        return None

    def fetch_previous_day_close(self, smart_api: SmartConnect, token: str) -> Optional[float]:
        """
        Fetch previous day's closing price
        """
        try:
            to_date_str = datetime.datetime.now().strftime('%Y-%m-%d 15:30')
            from_date_str = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%d 09:15')
            
            historic_req = {
                "exchange": "NSE",
                "symboltoken": token,
                "interval": "ONE_DAY",
                "fromdate": from_date_str,
                "todate": to_date_str
            }
            
            hist_data = self._smart_candle_fetch(smart_api, historic_req)
            
            if hist_data and hist_data.get('status') and hist_data.get('data'):
                candles = hist_data['data']
                if len(candles) >= 2:
                    # Get second last candle (previous day)
                    return candles[-2][4]  # Close price
        except Exception as e:
            print(f"PDC fetch error for token {token}: {e}")
        return None

    def fetch_historical_data(self, smart_api: SmartConnect, token: str) -> Optional[float]:
        """
        Fetch weekly close price
        Returns previous week's closing price
        """
        try:
            to_date_str = datetime.datetime.now().strftime('%Y-%m-%d 15:30')
            from_date_str = (datetime.datetime.now() - datetime.timedelta(days=45)).strftime('%Y-%m-%d 09:15')
            
            historic_req = {
                "exchange": "NSE",
                "symboltoken": token,
                "interval": "ONE_DAY",
                "fromdate": from_date_str,
                "todate": to_date_str
            }
            
            hist_data = self._smart_candle_fetch(smart_api, historic_req)
            
            if hist_data and hist_data.get('status') and hist_data.get('data'):
                candles = hist_data['data']
                today = datetime.date.today()
                current_week_monday = today - datetime.timedelta(days=today.weekday())
                
                print(f"Debug Hist Data {token}: Found {len(candles)} candles. Mon={current_week_monday}")
                
                # Find previous week's close
                for c in reversed(candles):
                    try:
                        c_date_str = c[0].split('T')[0]
                        c_date = datetime.datetime.strptime(c_date_str, "%Y-%m-%d").date()
                        if c_date < current_week_monday:
                            print(f"  Selected WC Candle: {c_date} Close={c[4]}")
                            return c[4]  # Close price
                    except:
                        continue
        except Exception as e:
            print(f"Historical data error for token {token}: {e}")
        return None

    def _smart_candle_fetch(self, smart_api: SmartConnect, req: Dict, retries: int = 3) -> Optional[Dict]:
        """
        Fetch candle data with retry logic
        """
        for i in range(retries):
            try:
                return smart_api.getCandleData(req)
            except Exception as e:
                err_msg = str(e)
                if "Couldn't parse" in err_msg or "timed out" in err_msg:
                    time.sleep(2 * (i + 1))
                    continue
                raise e
        return None

    def load_scrip_master(self):
        """
        Load NSE scrip master (cached for 24 hours)
        """
        try:
            # Check if file exists and is fresh
            if os.path.exists(SCRIPMASTER_FILE):
                file_age = time.time() - os.path.getmtime(SCRIPMASTER_FILE)
                if file_age < 86400:  # 24 hours
                    print("Loading Scrips from cache...")
                    with open(SCRIPMASTER_FILE, 'r') as f:
                        self.scrips = json.load(f)
                    self.master_loaded = True
                    print(f"Master Data Ready: {len(self.scrips)} symbols loaded.")
                    return
            
            # Download fresh data
            print("Downloading Scrip Master...")
            r = requests.get("https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json")
            data = r.json()
            
            # Filter NSE equity only
            self.scrips = [s for s in data if s.get('exch_seg') == 'NSE' and '-EQ' in s.get('symbol', '')]
            
            # Cache to file
            with open(SCRIPMASTER_FILE, 'w') as f:
                json.dump(self.scrips, f)
            
            self.master_loaded = True
            print(f"Master Data Ready: {len(self.scrips)} symbols loaded.")
            
        except Exception as e:
            print(f"Failed to load scrips: {e}")

    def search_symbols(self, query: str, limit: int = 15) -> List[Dict]:
        """
        Search symbols by prefix
        """
        if not self.master_loaded:
            return []
        
        query = query.upper()
        matches = [s for s in self.scrips if s['symbol'].startswith(query)]
        return matches[:limit]

# Global angel service instance
angel_service = AngelService()
