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
import threading
import collections

class TokenExpiredException(Exception):
    """Raised when the Angel One JWT token is expired or invalid"""
    pass

# Constants
if os.environ.get("K_SERVICE"):
    SCRIPMASTER_FILE = "/tmp/scripmaster.json"
else:
    # Fix: Scrip master is in the project root, not in backend/
    SCRIPMASTER_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "scripmaster.json")

class PriorityRateLimiter:
    """Global singleton limiter to enforce Angel's 3 req/sec for historical data"""
    def __init__(self, requests_per_second=2.5):
        self.delay = 1.0 / requests_per_second
        self.last_request_time = 0
        self.lock = threading.Lock()
        self.high_priority_queue = collections.deque()
        self.low_priority_queue = collections.deque()
        self.condition = threading.Condition(self.lock)
        self.running = True
        self.worker = threading.Thread(target=self._limiter_worker, daemon=True)
        self.worker.start()

    def wait_for_slot(self, priority='low'):
        event = threading.Event()
        with self.lock:
            if priority == 'high':
                self.high_priority_queue.append(event)
            else:
                self.low_priority_queue.append(event)
            self.condition.notify_all()
        event.wait()

    def _limiter_worker(self):
        while self.running:
            event = None
            with self.lock:
                while not self.high_priority_queue and not self.low_priority_queue:
                    self.condition.wait(timeout=1.0)
                    if not self.running: return

                if self.high_priority_queue:
                    event = self.high_priority_queue.popleft()
                elif self.low_priority_queue:
                    event = self.low_priority_queue.popleft()

            if event:
                now = time.time()
                elapsed = now - self.last_request_time
                if elapsed < self.delay:
                    time.sleep(self.delay - elapsed)
                
                self.last_request_time = time.time()
                event.set()

class AngelService:
    def __init__(self):
        self.scrips = []
        self.master_loaded = False
        # Caching layers
        self.candle_cache = {} # Key: (token, interval, fromdate, todate), Val: (ts, data)
        self.pd_cache = {} # Key: (token, date_str), Val: (ts, high, low, close)
        self.limiter = PriorityRateLimiter(requests_per_second=1.8) # Safer limit (1.8 req/sec)
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
                # Normalize: Strip "Bearer " if present (SDK generateSession adds it)
                raw_jwt = data['data']['jwtToken']
                if raw_jwt.startswith("Bearer "):
                    raw_jwt = raw_jwt.replace("Bearer ", "").strip()
                
                print(f"[OK] [ANGEL] Login Successful for {client_id}")
                smart_api.setUserId(client_id) # CRITICAL FIX: Explicitly set User ID
                tokens = {
                    'jwt_token': raw_jwt,
                    'feed_token': data['data']['feedToken'],
                    'refresh_token': data['data']['refreshToken']
                }
                return True, "Login Successful", smart_api, tokens
            else:
                return False, data.get('message', 'Unknown Login Error'), None, None
        except Exception as e:
            return False, str(e), None, None

    def refresh_access_token(self, smart_api: SmartConnect, refresh_token: str) -> Optional[Dict]:
        if not refresh_token:
            print("[ERR] [ANGEL] refresh_access_token: No refresh token provided")
            return None
            
        try:
            data = smart_api._postRequest('api.token', {"refreshToken": refresh_token})

            if data and data.get('status') and isinstance(data.get('data'), dict):
                d = data['data']
                jwt = d.get('jwtToken', '')
                # Strip Bearer if present
                if jwt.startswith("Bearer "):
                    jwt = jwt.replace("Bearer ", "").strip()
                
                feed = d.get('feedToken')
                refresh = d.get('refreshToken')

                # Update the smart_api instance manually like the SDK would have
                if jwt: smart_api.setAccessToken(jwt)
                if feed: smart_api.setFeedToken(feed)
                # Ensure userId is retained or re-set if available
                if hasattr(smart_api, 'userId') and smart_api.userId:
                    smart_api.setUserId(smart_api.userId)
                
                return {
                    'jwt_token': jwt,
                    'feed_token': feed,
                    'refresh_token': refresh
                }
            else:
                print(f"DEBUG: Token refresh raw response: {data}")
                msg = data.get('message', 'No message') if data else 'Empty response'
                code = data.get('errorcode', 'No code') if data else 'Unknown'
                print(f"[ERR] [ANGEL] Token renewal failed: {msg} ({code})")
        except Exception as e:
            print(f"[ERR] [ANGEL] Token refresh crash handled (likely SDK bug): {e}")
            import traceback
            traceback.print_exc()
        return None

    def logout(self, smart_api: SmartConnect) -> bool:
        try:
            if smart_api:
                smart_api.terminateSession(smart_api.client_id)
                return True
        except Exception as e:
            print(f"Angel logout error: {e}")
        return False

    def get_ltp_data(self, smart_api: SmartConnect, exchange: str, symbol: str, token: str) -> Optional[Dict]:
        try:
            res = smart_api.ltpData(exchange, symbol, token)
            if res and res.get('status') and res.get('data'):
                data = res.get('data')
                # PDC Optimization: Store the 'close' price as PDC in cache
                if data.get('close'):
                    p_close = float(data['close'])
                    cache_key = (str(token), "LATEST_PDC")
                    self.pd_cache[cache_key] = (time.time(), None, None, p_close)
                return data
            
            # Check for token expiration
            if res and isinstance(res, dict):
                err_code = res.get('errorcode')
                if err_code in ["AG8001", "AG8002", "AB1012"]:
                    print(f"[WARN] [ANGEL] Token Expired in get_ltp_data: {err_code}")
                    raise TokenExpiredException(f"Token expired: {err_code}")
        except TokenExpiredException:
            raise
        except Exception as e:
            print(f"LTP fetch error for {symbol}: {e}")
        return None

    def fetch_ltp(self, smart_api: SmartConnect, symbol: str, token: str, exchange: str = "NSE") -> Optional[float]:
        """Simple wrapper for backward compatibility and easy LTP access"""
        data = self.get_ltp_data(smart_api, exchange, symbol, token)
        if data and 'ltp' in data:
            return float(data['ltp'])
        return None

    def fetch_previous_day_close(self, smart_api: SmartConnect, token: str, exchange: str = "NSE") -> Optional[float]:
        # Check PDC cache first
        cache_key = (str(token), "LATEST_PDC")
        if cache_key in self.pd_cache:
            ts, _, _, c = self.pd_cache[cache_key]
            if time.time() - ts < 28800: # 8 hours
                if c is not None:
                    return c

        # If not in cache, try to get it from LTP data
        ltp_data = self.get_ltp_data(smart_api, exchange, "", token) # Symbol not strictly needed for LTP if token is there
        if ltp_data and ltp_data.get('close'):
            return float(ltp_data['close'])
        
        # Fallback to historical data if LTP doesn't provide it or fails
        try:
            pdh, pdl, pdc = self.fetch_previous_day_high_low(smart_api, token, exchange)
            return pdc
        except Exception as e:
            print(f"PDC fetch error for token {token}: {e}")
        return None

    def fetch_previous_day_high_low(self, smart_api: SmartConnect, token: str, exchange: str = "NSE", specific_date: Optional[str] = None, priority: str = 'low') -> Tuple[Optional[float], Optional[float], Optional[float]]:
        # 1. Check PDA (Previous Day Averages) Cache
        cache_date = specific_date or "LATEST"
        cache_key = (str(token), cache_date)
        
        # PDC specific check: If we only need PDC (cache_date == "LATEST") and it's in cache
        # (even if H/L are None), return it.
        if cache_key == (str(token), "LATEST") or cache_key == (str(token), "LATEST_PDC"):
            # Check both keys
            for k in [(str(token), "LATEST"), (str(token), "LATEST_PDC")]:
                if k in self.pd_cache:
                    ts, h, l, c = self.pd_cache[k]
                    if time.time() - ts < 28800: # 8 hours
                        # If we only need C (PDC) and we have it, return immediately
                        if not specific_date and c is not None:
                            # print(f"[CACHE] Optimized PDC return for {token}")
                            return h, l, c

        now = time.time()
        if cache_key in self.pd_cache:
            ts, h, l, c = self.pd_cache[cache_key]
            # PD values valid for 8 hours
            if now - ts < 28800:
                return h, l, c

        try:
            curr_now = datetime.datetime.now()
            if specific_date:
                from_date_str = f"{specific_date} 09:15"
                to_date_str = f"{specific_date} 15:30"
                interval = "ONE_MINUTE"
            else:
                to_date_str = curr_now.strftime('%Y-%m-%d %H:%M')
                from_date_str = (curr_now - datetime.timedelta(days=14)).strftime('%Y-%m-%d %H:%M')
                interval = "ONE_DAY"
            
            historic_req = {
                "exchange": exchange,
                "symboltoken": str(token),
                "interval": interval,
                "fromdate": from_date_str,
                "todate": to_date_str
            }
            
            # Use Priority for strategy-critical fetches
            hist_data = self._smart_candle_fetch(smart_api, historic_req, priority=priority)
            
            if hist_data and hist_data.get('status') and hist_data.get('data'):
                candles = hist_data['data']
                if not candles: return None, None, None
                
                h, l, c = None, None, None
                if specific_date:
                    h, l, close = -1.0, 99999999.0, candles[-1][4]
                    for cand in candles:
                        if cand[2] > h: h = cand[2]
                        if cand[3] < l: l = cand[3]
                    c = float(close)
                else:
                    today_str = curr_now.strftime('%Y-%m-%d')
                    target = candles[-2] if candles[-1][0].split('T')[0] == today_str and len(candles) >= 2 else candles[-1]
                    h, l, c = float(target[2]), float(target[3]), float(target[4])
                
                # Cache successful result
                if h is not None:
                    self.pd_cache[cache_key] = (time.time(), h, l, c)
                return h, l, c
        except Exception as e:
            print(f"PDH/L fetch error: {e}")
        return None, None, None

    def fetch_candle_data(self, smart_api: SmartConnect, req: Dict, priority: str = 'low') -> Optional[Dict]:
        return self._smart_candle_fetch(smart_api, req, priority=priority)

    def _smart_candle_fetch(self, smart_api: SmartConnect, req: Dict, retries: int = 3, priority: str = 'low') -> Optional[Dict]:
        # 1. Check Cache first (only for specific interval tags)
        token = str(req.get('symboltoken'))
        cache_key = (token, req.get('interval'), req.get('fromdate'), req.get('todate'))
        
        now = time.time()
        if cache_key in self.candle_cache:
            ts, data = self.candle_cache[cache_key]
            # 15m candles valid for 60s (to allow data finalization lag coverage)
            if now - ts < 60:
                # print(f"[CACHE] Returning cached candle for {token}")
                return data

        for i in range(retries):
            try:
                # Enforce global priority-based rate limit
                self.limiter.wait_for_slot(priority=priority)
                
                res = smart_api.getCandleData(req)
                
                if res and isinstance(res, dict) and not res.get('status'):
                    msg = str(res.get('message', '') or res.get('error', '')).lower()
                    code = str(res.get('errorcode', '') or res.get('errorCode', ''))
                    
                    if "too many requests" in msg or "rate limit" in msg or code in ["AB1004", "AB1019"]:
                        print(f"[WARN] [RATE-LIMIT] hit for {req.get('symboltoken')} ({priority}). Retrying in 12s... (Attempt {i+1}/{retries})")
                        time.sleep(12)
                        continue
                
                # Cache successful result
                if res and res.get('status'):
                    self.candle_cache[cache_key] = (time.time(), res)
                    # Cleanup old cache items occasionally
                    if len(self.candle_cache) > 200:
                        self.candle_cache = {k: v for k, v in self.candle_cache.items() if time.time() - v[0] < 3600}

                return res
            except Exception as e:
                err_str = str(e).lower()
                if "parse" in err_str or "timeout" in err_str:
                    time.sleep(2)
                    continue
                if "too many requests" in err_str or "rate limit" in err_str or "ab1004" in err_str or "ab1019" in err_str:
                    print(f"[WARN] Angel API Exception Rate Limit hit ({err_str[:50]}). Retrying in 12s... (Attempt {i+1}/{retries})")
                    time.sleep(12)
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
                with open(SCRIPMASTER_FILE, 'r', encoding='utf-8') as f:
                    self.scrips = json.load(f)
                
                # Ensure Core Indices are always present even if cache is old
                CORE_TOKENS = ["99926000", "99926009", "99919000", "99926012"]
                existing_tokens = {s['token'] for s in self.scrips}
                for core in [
                    {"token": "99926000", "symbol": "NIFTY 50", "exch_seg": "NSE"},
                    {"token": "99926009", "symbol": "NIFTY BANK", "exch_seg": "NSE"},
                    {"token": "99919000", "symbol": "SENSEX", "exch_seg": "BSE"},
                    {"token": "99926012", "symbol": "NIFTY FIN SERVICE", "exch_seg": "NSE"},
                    {"token": "99926000", "symbol": "NIFTY 50", "exch_seg": "NSE"},
                    {"token": "99926014", "symbol": "NIFTY IT", "exch_seg": "NSE"},
                    {"token": "99926037", "symbol": "NIFTY NEXT 50", "exch_seg": "NSE"},
                    {"token": "99926010", "symbol": "NIFTY ENERGY", "exch_seg": "NSE"}
                ]:
                    if core['token'] not in existing_tokens:
                        self.scrips.append(core)
                
                self.master_loaded = True
                print(f"[OK] {len(self.scrips)} symbols loaded from local file (including cores).")
                return

            # 2. Remote Download if local missing
            print("[INFO] Local cache missing, downloading from Angel One...")
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
            with open(SCRIPMASTER_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.scrips, f)
            
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

    # --- LIVE TRADING EXECUTION METHODS ---

    def place_order(self, smart_api: SmartConnect, order_params: Dict) -> Optional[str]:
        """
        Place an order with Angel One
        Params:
            symboltoken, transactiontype, exchange, ordertype, producttype, duration, price, squareoff, stoploss, quantity
        Returns:
            order_id if successful.
        Raises:
            Exception with error message if failed.
        """
        try:
            # Ensure quantity is integer
            if 'quantity' in order_params:
                order_params['quantity'] = str(int(float(order_params['quantity'])))
            
            # SDK v1.5.5 FIX: placeOrder(self, orderparams) takes ONE argument only.
            # 'variety' must remain INSIDE the params dict — do NOT pop it as a separate arg.
            if "variety" not in order_params:
                order_params["variety"] = "NORMAL"

            print(f"[EXEC] [LIVE] Placing Order: {order_params.get('tradingsymbol')} | {order_params.get('transactiontype')} x {order_params.get('quantity')} | {order_params.get('ordertype')} @ {order_params.get('price')} | variety={order_params.get('variety')}")

            response = smart_api.placeOrder(order_params)

            print(f"DEBUG: [ANGEL] Raw placeOrder Response: {response!r} (Type: {type(response).__name__})")

            # SDK returns the order ID string directly on success
            if isinstance(response, str) and len(response) > 0:
                print(f"[OK] [LIVE] Order Placed Successfully: OrderID={response}")
                return response

            # Handle Dictionary Return (some SDK versions / error paths)
            if isinstance(response, dict):
                if response.get('status') is False:
                    msg = response.get('message', 'Unknown Error')
                    code = response.get('errorcode', '')
                    print(f"[ERR] [ANGEL] placeOrder rejected: {msg} (code={code})")
                    if code in ["AG8001", "AG8002", "AB1012"]:
                        raise TokenExpiredException(f"Token expired: {code}")
                    raise Exception(f"{msg} (code={code})")

                if response.get('data') and 'orderid' in response['data']:
                    oid = response['data']['orderid']
                    print(f"[OK] [LIVE] Order Placed (dict path): OrderID={oid}")
                    return oid

                if 'orderid' in response:
                    return response['orderid']

            if response:
                print(f"[WARN] [LIVE] Ambiguous placeOrder Response: {response!r}")
                return str(response)

            # SDK returned None — means the API call failed internally
            print("[CRITICAL] Broker returned None/empty response.")
            print(f"[DEBUG] Order params sent: {json.dumps(order_params, indent=2)}")
            print(f"[DEBUG] SDK User: {getattr(smart_api, 'userId', 'UNKNOWN')}")
            raise Exception("Broker returned empty response — check VPS static IP whitelist and session validity")

        except Exception as e:
            print(f"[ERR] [LIVE] Place Order Exception: {e}")
            raise e

    def modify_order(self, smart_api: SmartConnect, order_params: Dict) -> Optional[Dict]:
        """
        Modify a pending order
        SDK v1.5.5: modifyOrder(self, orderparams) — variety stays inside the dict.
        """
        try:
            if "variety" not in order_params:
                order_params["variety"] = "NORMAL"
            print(f"[LIVE] Modifying Order: {order_params.get('orderid')} variety={order_params.get('variety')}")
            response = smart_api.modifyOrder(order_params)
            print(f"DEBUG: modifyOrder Response: {response!r}")
            return response
        except Exception as e:
            print(f"[ERR] [LIVE] Modify Order Error: {e}")
            return None

    def cancel_order(self, smart_api: SmartConnect, order_id: str, variety: str = "NORMAL") -> Optional[Dict]:
        """
        Cancel a pending order
        """
        try:
            print(f"[STOP] [LIVE] Cancelling Order: {order_id}")
            response = smart_api.cancelOrder(order_id, variety)
            return response
        except Exception as e:
            print(f"[ERR] [LIVE] Cancel Order Error: {e}")
            return None

    def get_order_book(self, smart_api: SmartConnect) -> Optional[List[Dict]]:
        """Fetch real order book"""
        try:
            data = smart_api.orderBook()
            if data and data.get('status'):
                return data.get('data')
            
            if data and isinstance(data, dict):
                err_code = data.get('errorcode')
                if err_code in ["AG8001", "AG8002", "AB1012"]:
                    print(f"[WARN] [ANGEL] Token Expired in orderBook: {err_code}")
                    raise TokenExpiredException(f"Token expired: {err_code}")
        except TokenExpiredException:
            raise
        except Exception as e:
            print(f"[ERR] [LIVE] Order Book Error: {e}")
        return None

    def get_trade_book(self, smart_api: SmartConnect) -> Optional[List[Dict]]:
        """Fetch executed trades"""
        try:
            data = smart_api.tradeBook()
            if data and data.get('status'):
                return data.get('data')
            
            if data and isinstance(data, dict):
                err_code = data.get('errorcode')
                if err_code in ["AG8001", "AG8002", "AB1012"]:
                    print(f"[WARN] [ANGEL] Token Expired in tradeBook: {err_code}")
                    raise TokenExpiredException(f"Token expired: {err_code}")
        except TokenExpiredException:
            raise
        except Exception as e:
            print(f"[ERR] [LIVE] Trade Book Error: {e}")
        return None

    def get_position(self, smart_api: SmartConnect) -> Optional[List[Dict]]:
        """Fetch net positions"""
        try:
            data = smart_api.position()
            if data and data.get('status'):
                return data.get('data')
            
            # Check for token expiration
            if data and isinstance(data, dict):
                err_code = data.get('errorcode')
                if err_code in ["AG8001", "AG8002", "AB1012"]:
                    print(f"[WARN] [ANGEL] Token Expired in get_position: {err_code}")
                    raise TokenExpiredException(f"Token expired: {err_code}")
                    
        except TokenExpiredException:
            raise
        except Exception as e:
            print(f"[ERR] [LIVE] Position Error: {e}")
        return None

    def get_rms_limit(self, smart_api: SmartConnect) -> Optional[Dict]:
        """Fetch funds and margin limits"""
        try:
            data = smart_api.rmsLimit()
            # The API might return different structures, we return data safely
            if data and data.get('status'):
                return data.get('data')
            
            # Check for token expiration
            if data and isinstance(data, dict):
                err_code = data.get('errorcode')
                if err_code in ["AG8001", "AG8002", "AB1012"]:
                    print(f"[WARN] [ANGEL] Token Expired in get_rms_limit: {err_code}")
                    raise TokenExpiredException(f"Token expired: {err_code}")

            # Fallback if structure is different (sometimes data IS the dict)
            if data and isinstance(data, dict) and 'net' in data:
                return data
        except TokenExpiredException:
            raise
        except Exception as e:
            print(f"[ERR] [LIVE] RMS Limit Error: {e}")
        return None

    def get_error_message(self, error_code: str) -> str:
        """Map Angel One error codes to human-readable explanations"""
        mapping = {
            "AG8001": "Invalid Token - Your session has expired or the token is malformed.",
            "AG8002": "Invalid Refresh Token - Cannot renew session. Please log in again.",
            "AG8003": "Invalid Client ID - Check your login credentials.",
            "AG8004": "Invalid API Key - The API Key being used is blocked or incorrect.",
            "AB1012": "Authentication Failure - JWT token missing or session killed by broker.",
            "AB1004": "Too Many Requests - Rate limit exceeded (Historical data max 3 req/sec).",
            "AB2000": "Internal Error - Angel One server is experiencing issues.",
            "EN4001": "Invalid Request - Checklist: Is token correct? Is exchange correct?"
        }
        return mapping.get(error_code, f"Unknown Angel Error ({error_code})")

angel_service = AngelService()