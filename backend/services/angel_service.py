"""
Angel One API Service - GCP Optimized
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

SCRIPMASTER_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripmaster.json")

class AngelService:
    def __init__(self):
        self.scrips = []
        self.master_loaded = False
        # Pre-load core scrips for instant search during startup
        self._load_core_scrips()

    def _load_core_scrips(self):
        """Load common indices and top stocks immediately for 'Zero-Wait' search"""
        CORE_SCRIPS = [
            {"token": "99926000", "symbol": "NIFTY 50", "exch_seg": "NSE"},
            {"token": "99926009", "symbol": "NIFTY BANK", "exch_seg": "NSE"},
            {"token": "99926012", "symbol": "NIFTY FIN SERVICE", "exch_seg": "NSE"},
            {"token": "99919000", "symbol": "SENSEX", "exch_seg": "BSE"},
            {"token": "99926013", "symbol": "NIFTY IT", "exch_seg": "NSE"},
            {"token": "99926023", "symbol": "NIFTY PHARMA", "exch_seg": "NSE"},
            {"token": "99926003", "symbol": "NIFTY AUTO", "exch_seg": "NSE"},
            {"token": "99926011", "symbol": "NIFTY FMCG", "exch_seg": "NSE"},
            {"token": "99926015", "symbol": "NIFTY METAL", "exch_seg": "NSE"},
            {"token": "99926024", "symbol": "NIFTY REALTY", "exch_seg": "NSE"},
            {"token": "99926010", "symbol": "NIFTY ENERGY", "exch_seg": "NSE"},
            {"token": "3045", "symbol": "SBIN-EQ", "exch_seg": "NSE"},
            {"token": "1333", "symbol": "HDFCBANK-EQ", "exch_seg": "NSE"},
            {"token": "1594", "symbol": "INFY-EQ", "exch_seg": "NSE"},
            {"token": "2885", "symbol": "RELIANCE-EQ", "exch_seg": "NSE"},
            {"token": "10604", "symbol": "ICICIBANK-EQ", "exch_seg": "NSE"},
            {"token": "11536", "symbol": "TCS-EQ", "exch_seg": "NSE"},
            {"token": "5900", "symbol": "AXISBANK-EQ", "exch_seg": "NSE"},
            {"token": "1922", "symbol": "KOTAKBANK-EQ", "exch_seg": "NSE"},
            {"token": "11483", "symbol": "LT-EQ", "exch_seg": "NSE"},
            {"token": "1660", "symbol": "ITC-EQ", "exch_seg": "NSE"},
            {"token": "1232", "symbol": "HCLTECH-EQ", "exch_seg": "NSE"},
            {"token": "3101", "symbol": "TATAMOTORS-EQ", "exch_seg": "NSE"}
        ]
        self.scrips = CORE_SCRIPS
        self.master_loaded = True # Allow search for these immediately

    def login(self, api_key: str, client_id: str, password: str, totp_secret: str) -> Tuple[bool, str, Optional[SmartConnect], Optional[Dict]]:
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

    def logout(self, smart_api: SmartConnect) -> bool:
        try:
            if smart_api:
                smart_api.terminateSession(smart_api.client_id)
                return True
        except Exception as e:
            print(f"Angel logout error: {e}")
        return False

    def fetch_ltp(self, smart_api: SmartConnect, symbol: str, token: str, exchange: str = "NSE") -> Optional[float]:
        try:
            ltp_data = smart_api.ltpData(exchange, symbol, token)
            if ltp_data and ltp_data.get('status'):
                return ltp_data['data']['ltp']
        except Exception as e:
            print(f"LTP fetch error for {symbol}: {e}")
        return None

    def fetch_previous_day_close(self, smart_api: SmartConnect, token: str, exchange: str = "NSE") -> Optional[float]:
        try:
            pdh, pdl, pdc = self.fetch_previous_day_high_low(smart_api, token, exchange)
            return pdc
        except Exception as e:
            print(f"PDC fetch error for token {token}: {e}")
        return None

    def fetch_previous_day_high_low(self, smart_api: SmartConnect, token: str, exchange: str = "NSE", specific_date: Optional[str] = None) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        try:
            now = datetime.datetime.now()
            if specific_date:
                from_date_str = f"{specific_date} 09:15"
                to_date_str = f"{specific_date} 15:30"
                interval = "ONE_MINUTE"
            else:
                to_date_str = now.strftime('%Y-%m-%d %H:%M')
                from_date_str = (now - datetime.timedelta(days=14)).strftime('%Y-%m-%d %H:%M')
                interval = "ONE_DAY"
            
            historic_req = {
                "exchange": exchange,
                "symboltoken": str(token),
                "interval": interval,
                "fromdate": from_date_str,
                "todate": to_date_str
            }
            
            print(f"DEBUG: SmartAPI req: {historic_req}")
            hist_data = self._smart_candle_fetch(smart_api, historic_req)
            print(f"DEBUG: Hist data status: {hist_data.get('status') if hist_data else 'None'}")
            
            if hist_data and hist_data.get('status') and hist_data.get('data'):
                candles = hist_data['data']
                if not candles: return None, None, None
                
                if specific_date:
                    high, low, close = -1.0, 99999999.0, candles[-1][4]
                    for c in candles:
                        if c[2] > high: high = c[2]
                        if c[3] < low: low = c[3]
                    return float(high), float(low), float(close)
                else:
                    today_str = now.strftime('%Y-%m-%d')
                    target = candles[-2] if candles[-1][0].split('T')[0] == today_str and len(candles) >= 2 else candles[-1]
                    return float(target[2]), float(target[3]), float(target[4])
        except Exception as e:
            print(f"PDH/L fetch error: {e}")
        return None, None, None

    def fetch_candle_data(self, smart_api: SmartConnect, req: Dict) -> Optional[Dict]:
        return self._smart_candle_fetch(smart_api, req)

    def _smart_candle_fetch(self, smart_api: SmartConnect, req: Dict, retries: int = 3) -> Optional[Dict]:
        for i in range(retries):
            try:
                return smart_api.getCandleData(req)
            except Exception as e:
                err_str = str(e).lower()
                if "parse" in err_str or "timeout" in err_str:
                    time.sleep(2)
                    continue
                if "too many requests" in err_str or "rate limit" in err_str or "throttle" in err_str:
                    print(f"[WARN] Angel API Rate Limit hit. Retrying in 5s... (Attempt {i+1}/{retries})")
                    time.sleep(5)
                    continue
                raise e
        return None

    def load_scrip_master(self):
        """
        Load NSE scrip master - Optimized for Speed & GCP Persistence
        """
        try:
            # 1. Try local JSON file first (fastest)
            if os.path.exists(SCRIPMASTER_FILE):
                print("[INFO] Loading Scrips from local cache...")
                with open(SCRIPMASTER_FILE, 'r') as f:
                    self.scrips = json.load(f)
                
                # Ensure Core Indices are always present even if cache is old
                CORE_TOKENS = ["99926000", "99926009", "99919000", "99926012"]
                existing_tokens = {s['token'] for s in self.scrips}
                for core in [
                    {"token": "99926000", "symbol": "NIFTY 50", "exch_seg": "NSE"},
                    {"token": "99926009", "symbol": "NIFTY BANK", "exch_seg": "NSE"},
                    {"token": "99919000", "symbol": "SENSEX", "exch_seg": "BSE"},
                    {"token": "99926012", "symbol": "NIFTY FIN SERVICE", "exch_seg": "NSE"}
                ]:
                    if core['token'] not in existing_tokens:
                        self.scrips.append(core)
                
                self.master_loaded = True
                print(f"[OK] {len(self.scrips)} symbols loaded from local file (including cores).")
                return

            # 2. Try GCS if local missing
            bucket_name = os.getenv("GCS_BUCKET_NAME")
            if bucket_name:
                try:
                    from google.cloud import storage
                    client = storage.Client()
                    bucket = client.bucket(bucket_name)
                    blob = bucket.blob("scripmaster.json")
                    if blob.exists():
                        print("[INFO] Downloading Scrip Master from GCS...")
                        blob.download_to_filename(SCRIPMASTER_FILE)
                        with open(SCRIPMASTER_FILE, 'r') as f:
                            self.scrips = json.load(f)
                        self.master_loaded = True
                        print(f"[OK] Loaded {len(self.scrips)} symbols from GCS.")
                        return
                except Exception as ge:
                    print(f"[WARN] GCS Scrip Master check failed: {ge}")

            # 3. Remote Download if both missing
            print("[INFO] Local and GCS cache missing, downloading from Angel One...")
            r = requests.get("https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json", timeout=15)
            data = r.json()
            
            # Filter for NSE Stocks (-EQ) and common Indices
            indices_tokens = [
                "99926000", "99926009", "99926012", "99926014", "99919000", 
                "99926013", "99926023", "99926003", "99926011", "99926015", 
                "99926024", "99926010", "99926037", "99926005"
            ]
            full_scrips = [
                {"token": s.get('token'), "symbol": s.get('symbol'), "exch_seg": s.get('exch_seg')}
                for s in data 
                if (s.get('exch_seg') == 'NSE' and '-EQ' in s.get('symbol', '')) or 
                   (s.get('exch_seg') == 'BSE' and '-EQ' in s.get('symbol', '')) or
                   (s.get('token') in indices_tokens)
            ]
            
            self.scrips = full_scrips
            
            # Save locally
            with open(SCRIPMASTER_FILE, 'w') as f:
                json.dump(self.scrips, f)
            
            # Sync to GCS
            if bucket_name:
                try:
                    blob.upload_from_filename(SCRIPMASTER_FILE)
                    print(f"[INFO] Synced Scrip Master to GCS bucket: {bucket_name}")
                except Exception as ue:
                    print(f"[ERROR] GCS Scrip Upload failed: {ue}")

            self.master_loaded = True
            print(f"[OK] Downloaded and cached {len(self.scrips)} symbols.")
            
        except Exception as e:
            print(f"[ERROR] Scrip Master Error: {e}")
            
        finally:
            pass

    def search_symbols(self, query: str, limit: int = 15) -> List[Dict]:
        """
        In-memory search - extremely fast.
        If full master isn't loaded, it searches the Core Scrips.
        """
        if not self.scrips:
            return []
            
        query = query.upper()
        
        # Optimized search: 
        # 1. First find stocks that START with the query
        # 2. Then find stocks that CONTAIN the query
        # This is much faster than sorting tens of thousands of items
        
        prefix_matches = []
        contain_matches = []
        
        for s in self.scrips:
            symbol = s['symbol']
            if symbol.startswith(query):
                prefix_matches.append(s)
            elif query in symbol:
                contain_matches.append(s)
            
            # Stop early if we have enough prefix matches to fill the limit
            if len(prefix_matches) >= limit:
                break
                
        # Combine and trim
        results = prefix_matches[:limit]
        if len(results) < limit:
            results.extend(contain_matches[:(limit - len(results))])
            
        return results

angel_service = AngelService()