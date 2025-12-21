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
            pdh, pdl, pdc = self.fetch_previous_day_high_low(smart_api, token)
            return pdc
        except Exception as e:
            print(f"PDC fetch error for token {token}: {e}")
        return None

    def fetch_previous_day_high_low(self, smart_api: SmartConnect, token: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Fetch High, Low, and Close for the last completed trading day
        Returns: (high, low, close)
        """
        try:
            # Broaden range to 14 days to handle holidays
            # For ONE_DAY interval, using just date usually works better
            now = datetime.datetime.now()
            to_date_str = now.strftime('%Y-%m-%d %H:%M')
            from_date_str = (now - datetime.timedelta(days=14)).strftime('%Y-%m-%d %H:%M')
            
            historic_req = {
                "exchange": "NSE",
                "symboltoken": str(token),
                "interval": "ONE_DAY",
                "fromdate": from_date_str,
                "todate": to_date_str
            }
            
            # Detailed logging for troubleshooting
            # print(f"DEBUG: SmartAPI Request: {historic_req}")
            hist_data = self._smart_candle_fetch(smart_api, historic_req)
            
            if hist_data and hist_data.get('status') and hist_data.get('data'):
                candles = hist_data['data']
                if not candles: 
                    print(f"DEBUG: No candles returned for token {token}")
                    return None, None, None
                
                print(f"DEBUG: Total candles for {token}: {len(candles)}")
                print(f"DEBUG: First candle raw: {candles[0]}")
                
                # Get last candle and check if it's today
                today_str = now.strftime('%Y-%m-%d')
                last_candle = candles[-1]
                last_candle_date = last_candle[0].split('T')[0]
                
                if last_candle_date == today_str:
                    if len(candles) >= 2:
                        target = candles[-2]
                        # print(f"DEBUG: Last candle is today ({today_str}), using penultimate candle ({target[0]})")
                    else:
                        # Only one candle and it's today... maybe first day of trading for this token?
                        target = last_candle
                        print(f"DEBUG: Only one candle found and it is today ({today_str}). Using it.")
                else:
                    target = last_candle
                    # print(f"DEBUG: Last candle ({last_candle_date}) is not today ({today_str}). Using last candle.")
                
                # [timestamp, open, high, low, close, volume]
                return float(target[2]), float(target[3]), float(target[4])
            else:
                status_msg = hist_data.get('message', 'No message') if hist_data else 'No response'
                print(f"DEBUG: SmartAPI Error for token {token}: {status_msg}")
        except Exception as e:
            print(f"PDH/L fetch error for token {token}: {e}")
        return None, None, None

    def fetch_candle_data(self, smart_api: SmartConnect, req: Dict) -> Optional[Dict]:
        """
        Public wrapper to fetch candle data
        """
        return self._smart_candle_fetch(smart_api, req)

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
