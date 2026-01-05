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

    def logout(self, smart_api: SmartConnect) -> bool:
        """
        Terminate session with Angel One
        """
        try:
            if smart_api:
                smart_api.terminateSession(smart_api.client_id)
                return True
        except Exception as e:
            print(f"Angel logout error: {e}")
        return False

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

    def fetch_previous_day_close(self, smart_api: SmartConnect, token: str, exchange: str = "NSE") -> Optional[float]:
        """
        Fetch previous day's closing price
        """
        try:
            pdh, pdl, pdc = self.fetch_previous_day_high_low(smart_api, token, exchange)
            return pdc
        except Exception as e:
            print(f"PDC fetch error for token {token}: {e}")
        return None

    def fetch_previous_day_high_low(self, smart_api: SmartConnect, token: str, exchange: str = "NSE", specific_date: Optional[str] = None) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Fetch High, Low, and Close for a specific date OR the last completed trading day
        Returns: (high, low, close)
        """
        try:
            now = datetime.datetime.now()
            
            if specific_date:
                # Use the exact date requested
                from_date_str = f"{specific_date} 09:15"
                to_date_str = f"{specific_date} 15:30"
                interval = "ONE_MINUTE" # Use minute data for high precision on a specific day
            else:
                # Broaden range to 14 days to handle holidays for finding "Last Completed Day"
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
            
            hist_data = self._smart_candle_fetch(smart_api, historic_req)
            
            if hist_data and hist_data.get('status') and hist_data.get('data'):
                candles = hist_data['data']
                if not candles: 
                    print(f"DEBUG: No candles returned for token {token} on {specific_date if specific_date else 'last-day'}")
                    return None, None, None
                
                if specific_date:
                    # Calculate High/Low/Close from minute candles
                    high = -1.0
                    low = 99999999.0
                    close = candles[-1][4]
                    for c in candles:
                        if c[2] > high: high = c[2]
                        if c[3] < low: low = c[3]
                    return float(high), float(low), float(close)
                else:
                    # Original logic for finding previous trading day
                    today_str = now.strftime('%Y-%m-%d')
                    last_candle = candles[-1]
                    last_candle_date = last_candle[0].split('T')[0]
                    
                    if last_candle_date == today_str:
                        if len(candles) >= 2:
                            target = candles[-2]
                        else:
                            target = last_candle
                    else:
                        target = last_candle
                    
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
        Load NSE scrip master (DB first, then fallback to JSON, then download)
        """
        from database import SessionLocal
        from models import ScripMaster, SystemMetadata
        from sqlalchemy import delete
        
        db = SessionLocal()
        try:
            # 1. Check DB for metadata
            meta = db.query(SystemMetadata).filter(SystemMetadata.key == "scripmaster_updated").first()
            if meta:
                # Check if fresh (24h)
                age = (datetime.datetime.utcnow() - meta.updated_at).total_seconds()
                if age < 86400:
                    print("Loading Scrip Master from SQL Cache...")
                    db_scrips = db.query(ScripMaster).all()
                    if db_scrips:
                        self.scrips = [
                            {
                                "token": s.token,
                                "symbol": s.symbol,
                                "name": s.name,
                                "exch_seg": s.exch_seg,
                                "expiry": s.expiry,
                                "strike": s.strike,
                                "lotsize": s.lotsize,
                                "instrumenttype": s.instrumenttype,
                                "tick_size": s.tick_size
                            } for s in db_scrips
                        ]
                        self.master_loaded = True
                        print(f"Master Data Ready (SQL): {len(self.scrips)} symbols.")
                        return

            # 2. Fallback to scripmaster.json for local development speed
            if os.path.exists(SCRIPMASTER_FILE):
                file_age = time.time() - os.path.getmtime(SCRIPMASTER_FILE)
                if file_age < 86400:
                    print("Loading Scrip Master from JSON fallback...")
                    with open(SCRIPMASTER_FILE, 'r') as f:
                        self.scrips = json.load(f)
                    self.master_loaded = True
                    print(f"Master Data Ready (JSON): {len(self.scrips)} symbols.")
                    # Sync to DB if DB was empty
                    if not meta:
                        self._sync_scrips_to_db(db)
                    return
            
            # 3. Download fresh data
            print("Downloading Scrip Master from Angel One...")
            r = requests.get("https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json")
            data = r.json()
            
            # Filter NSE equity only
            self.scrips = [s for s in data if s.get('exch_seg') == 'NSE' and '-EQ' in s.get('symbol', '')]
            
            # Cache to file (fallback)
            with open(SCRIPMASTER_FILE, 'w') as f:
                json.dump(self.scrips, f)
            
            # Sync to Database
            self._sync_scrips_to_db(db)
            
            self.master_loaded = True
            print(f"Master Data Ready (Download): {len(self.scrips)} symbols.")
            
        except Exception as e:
            print(f"Failed to load scrips: {e}")
        finally:
            db.close()

    def _sync_scrips_to_db(self, db):
        """Helper to bulk insert scrips into DB"""
        from models import ScripMaster, SystemMetadata
        from sqlalchemy import delete
        try:
            print("Syncing Scrips to SQL Database...")
            db.execute(delete(ScripMaster))
            
            # Bulk insert
            db.bulk_insert_mappings(ScripMaster, [
                {
                    "token": s.get('token'),
                    "symbol": s.get('symbol'),
                    "name": s.get('name'),
                    "exch_seg": s.get('exch_seg'),
                    "expiry": s.get('expiry'),
                    "strike": s.get('strike'),
                    "lotsize": s.get('lotsize'),
                    "instrumenttype": s.get('instrumenttype'),
                    "tick_size": s.get('tick_size')
                } for s in self.scrips
            ])
            
            # Update metadata
            meta = db.query(SystemMetadata).filter(SystemMetadata.key == "scripmaster_updated").first()
            if not meta:
                meta = SystemMetadata(key="scripmaster_updated")
                db.add(meta)
            meta.value = str(len(self.scrips))
            meta.updated_at = datetime.datetime.utcnow()
            
            db.commit()
            print("Sync Complete.")
        except Exception as e:
            db.rollback()
            print(f"Sync failed: {e}")

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
