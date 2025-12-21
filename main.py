import websocket # Make sure you have 'pip install websocket-client'
import flet as ft
import requests
import pyotp
import threading
import time
import uuid
import datetime
import traceback
import json
import os
import queue
import struct
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2

# --- CONSTANTS ---
CONFIG_FILE = "config.json"
SCRIPMASTER_FILE = "scripmaster.json"

# --- GLOBAL JOB QUEUE ---
api_job_queue = queue.Queue()

def api_worker_thread():
    while True:
        try:
            task = api_job_queue.get()
            if task is None: break 
            
            func, args, page_ref = task
            func(*args)
            
            if page_ref:
                try: page_ref.update()
                except: pass
                
        except Exception as e:
            print(f"Worker Error: {e}")
        finally:
            if 'task' in locals() and task is not None:
                api_job_queue.task_done()
            time.sleep(2.0) 

threading.Thread(target=api_worker_thread, daemon=True).start()


class AppState:
    def __init__(self):
        self.api_key = ""
        self.client_id = ""
        self.jwt_token = None
        self.feed_token = None
        self.refresh_token = None
        self.smart_api = None
        self.sws = None
        
        self.current_view = "watchlist"
        self.scrips = []
        self.live_feed_status = "DISCONNECTED"
        self.master_loaded = False
        
        self.watchlist = []
        self.alerts = []
        self.logs = []
        self.is_paused = False
        self.connected = False
        
        # UI Reference storage
        self.feed_status_control = None 
        
        # Filter and sort state
        self.filter_symbol = ""
        self.filter_min_price = ""
        self.filter_max_price = ""
        self.sort_by = "none"

state = AppState()

# --- HELPERS ---
def load_config():
    default = {"api_key": "", "client_id": "", "watchlist": []}
    if not os.path.exists(CONFIG_FILE): return default
    try:
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            if "watchlist" not in data: data["watchlist"] = []
            return data
    except: return default

def save_config():
    # Create a clean copy of watchlist without UI controls
    clean_watchlist = []
    for stock in state.watchlist:
        # Filter out Flet controls (keys ending in _control)
        clean_stock = {k: v for k, v in stock.items() if not k.endswith('_control')}
        clean_watchlist.append(clean_stock)

    data = {
        "api_key": state.api_key,
        "client_id": state.client_id,
        "watchlist": clean_watchlist
    }
    try:
        with open(CONFIG_FILE, 'w') as f: json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

def load_scrips(page=None):
    def _background_load():
        try:
            # Cache scrip master for 24 hours
            if not os.path.exists(SCRIPMASTER_FILE) or (time.time() - os.path.getmtime(SCRIPMASTER_FILE) > 86400):
                print("Downloading Scrip Master...")
                r = requests.get("https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json")
                data = r.json()
                # Filter for NSE Equity only to save memory
                state.scrips = [s for s in data if s.get('exch_seg') == 'NSE' and '-EQ' in s.get('symbol', '')]
                with open(SCRIPMASTER_FILE, 'w') as f: json.dump(state.scrips, f)
            else:
                print("Loading Scrips from cache...")
                with open(SCRIPMASTER_FILE, 'r') as f: state.scrips = json.load(f)
            
            state.master_loaded = True
            print(f"Master Data Ready: {len(state.scrips)} symbols loaded.")
            if page:
                try: page.update() 
                except: pass
        except Exception as e:
            print(f"Failed to load scrips: {e}")

    threading.Thread(target=_background_load, daemon=True).start()

def angel_login(api_key, client_id, password, totp_secret):
    try:
        smartApi = SmartConnect(api_key=api_key)
        totp_val = pyotp.TOTP(totp_secret).now()
        data = smartApi.generateSession(client_id, password, totp_val)
        
        if data.get('status'):
            state.smart_api = smartApi
            state.jwt_token = data['data']['jwtToken']
            state.feed_token = data['data']['feedToken']
            state.refresh_token = data['data']['refreshToken']
            return True, "Login Successful"
        else:
            return False, data.get('message', 'Unknown Login Error')
    except Exception as e:
        return False, str(e)

def fetch_initial_ltp():
    """Fetch just the LTP (current price) for all stocks via REST API once"""
    if not state.smart_api or not state.watchlist:
        return
    
    def _fetch():
        for stock in state.watchlist:
            try:
                ltp_data = state.smart_api.ltpData("NSE", stock['symbol'], stock['token'])
                if ltp_data and ltp_data.get('status'):
                    stock['ltp'] = ltp_data['data']['ltp']
                    print(f"Fetched LTP for {stock['symbol']}: ₹{stock['ltp']:.2f}")
            except Exception as e:
                print(f"LTP fetch error for {stock['symbol']}: {e}")
    
    threading.Thread(target=_fetch, daemon=True).start()


# --- SMART DATA FETCHING ---
def smart_candle_fetch(req):
    """Retries candle fetching with backoff."""
    retries = 3
    for i in range(retries):
        try:
            return state.smart_api.getCandleData(req)
        except Exception as e:
            err_msg = str(e)
            if "Couldn't parse" in err_msg or "timed out" in err_msg or "Max retries" in err_msg:
                wait = 2 * (i + 1)
                time.sleep(wait)
                continue
            raise e 
    return None

def fetch_historical_data_task(stock_item):
    """Fetches historical data to find previous week's close"""
    if not state.smart_api: return
    
    try:
        stock_item['loading'] = True
        
        # 1. Fetch LTP (Fast check via REST if WS isn't ready)
        try:
            ltp_data = state.smart_api.ltpData("NSE", stock_item['symbol'], stock_item['token'])
            if ltp_data and ltp_data.get('status'):
                stock_item['ltp'] = ltp_data['data']['ltp']
        except: pass

        # 2. Fetch History (Previous Week Close Logic)
        need_fetch = True
        if stock_item.get('wc') and stock_item.get('wc_fetched_at'):
            try:
                last_fetch = datetime.datetime.fromisoformat(stock_item['wc_fetched_at'])
                if last_fetch.isocalendar()[:2] == datetime.datetime.now().isocalendar()[:2]:
                    need_fetch = False
            except: pass
            
        if need_fetch:
            try:
                to_date_str = datetime.datetime.now().strftime('%Y-%m-%d 15:30')
                from_date_str = (datetime.datetime.now() - datetime.timedelta(days=45)).strftime('%Y-%m-%d 09:15')
                
                historic_req = {
                    "exchange": "NSE",
                    "symboltoken": stock_item['token'],
                    "interval": "ONE_DAY",
                    "fromdate": from_date_str,
                    "todate": to_date_str
                }
                
                hist_data = smart_candle_fetch(historic_req)
                
                if hist_data and hist_data.get('status') and hist_data.get('data'):
                    candles = hist_data['data']
                    today = datetime.date.today()
                    current_week_monday = today - datetime.timedelta(days=today.weekday())
                    
                    found = False
                    for c in reversed(candles):
                        try:
                            c_date_str = c[0].split('T')[0]
                            c_date = datetime.datetime.strptime(c_date_str, "%Y-%m-%d").date()
                            if c_date < current_week_monday:
                                stock_item['wc'] = c[4] 
                                stock_item['wc_fetched_at'] = datetime.datetime.now().isoformat()
                                found = True
                                print(f"Found Prev Week Close for {stock_item['symbol']}: {stock_item['wc']}")
                                break
                        except: continue
                    if not found: print(f"No prev week candle found for {stock_item['symbol']}")
            except Exception as e:
                print(f"Candle Error {stock_item['symbol']}: {e}")

    except Exception as e:
        print(f"Task Failed for {stock_item['symbol']}: {e}")
    finally:
        stock_item['loading'] = False

def refresh_all_data(page):
    for stock in state.watchlist:
        stock['loading'] = True
        api_job_queue.put((fetch_historical_data_task, [stock], page))
    try: page.update()
    except: pass

# --- WEBSOCKET ---
def start_websocket(page):
    if not all([state.jwt_token, state.api_key, state.client_id, state.feed_token]): 
        print("Websocket: Missing tokens")
        return

    # Disable trace now that we know data is coming (keeps terminal clean)
    # websocket.enableTrace(True) 

    try:
        state.sws = SmartWebSocketV2(state.jwt_token, state.api_key, state.client_id, state.feed_token)
    except Exception as e:
        print(f"Websocket Init Error: {e}")
        return
    
    # Map for O(1) Lookup
    token_map = {str(s['token']): s for s in state.watchlist}

    def on_data(wsapp, message):
        try:
            # 1. Handle Standard List/Dict (If SDK works correctly)
            if isinstance(message, (list, dict)):
                if isinstance(message, dict): message = [message]
                for tick in message:
                    token = tick.get('token') or tick.get('tk')
                    raw_price = tick.get('last_traded_price') or tick.get('ltp') or tick.get('c')
                    
                    if token and raw_price is not None:
                        stock = token_map.get(str(token))
                        if stock:
                            if 'last_traded_price' in tick:
                                stock['ltp'] = float(raw_price) / 100.0
                            else:
                                stock['ltp'] = float(raw_price)
                            check_alerts(stock, page)

            # 2. MANUALLY PARSE BINARY (The Fix for your issue)
            # Based on Angel One Binary Format:
            # Byte 0-1: Header | 2-27: Token (25b) | 27-35: Seq | 35-43: Time | 43-51: LTP (8b)
            elif isinstance(message, bytes):
                try:
                    # Extract Token (Bytes 2 to 27, strip nulls)
                    token_bytes = message[2:27]
                    token = token_bytes.replace(b'\x00', b'').decode('utf-8')
                    
                    # Extract LTP (Bytes 43 to 51, Little Endian Long Long)
                    # We ensure message is long enough (Mode 3 is usually > 50 bytes)
                    if len(message) > 50:
                        ltp_bytes = message[43:51]
                        ltp_paise = struct.unpack('<q', ltp_bytes)[0]
                        real_price = ltp_paise / 100.0
                        
                        # Update State
                        stock = token_map.get(str(token))
                        if stock:
                            stock['ltp'] = real_price
                            # print(f"BinTick: {stock['symbol']} -> {real_price}") # Debug
                            check_alerts(stock, page)
                except Exception as e:
                    print(f"Binary Parse Error: {e}")

        except Exception as e: 
            print(f"General Parse Error: {e}")

    def on_open(wsapp):
        print("Websocket: Connected")
        state.live_feed_status = "CONNECTED"
        time.sleep(1)
        
        token_map.update({str(s['token']): s for s in state.watchlist})
        token_list = [item['token'] for item in state.watchlist]
        
        if token_list:
            try:
                token_list_str = [str(t) for t in token_list]
                # Keep Mode 3 (Snap Quote) as it's the most reliable
                state.sws.subscribe("watchlist", 3, [{"exchangeType": 1, "tokens": token_list_str}])
                print(f"Websocket: Subscribed to {len(token_list_str)} tokens")
            except Exception as e:
                print(f"Websocket Subscribe Error: {e}")

    def on_close(wsapp, code, reason):
        print(f"Websocket: Closed {code} {reason}")
        state.live_feed_status = "DISCONNECTED"
            
    def on_error(wsapp, error):
        print(f"Websocket Error: {error}")
        state.live_feed_status = "ERROR"

    state.sws.on_data = on_data
    state.sws.on_open = on_open
    state.sws.on_close = on_close
    state.sws.on_error = on_error
    
    print("Websocket: Connecting...")
    threading.Thread(target=state.sws.connect, daemon=True).start()

# --- ALERT LOGIC ---
def check_alerts(stock, page):
    if state.is_paused: return
    triggered_something = False
    for alert in list(state.alerts):
        if str(alert["token"]) == str(stock["token"]):
            triggered = False
            if alert["condition"] == "ABOVE" and stock["ltp"] >= alert["price"]: triggered = True
            elif alert["condition"] == "BELOW" and stock["ltp"] <= alert["price"]: triggered = True
            
            if triggered:
                msg = f"{stock['symbol']} hit {alert['price']} ({alert['condition']})"
                state.logs.insert(0, {"time": datetime.datetime.now().strftime("%H:%M:%S"), "symbol": stock['symbol'], "msg": msg})
                if alert in state.alerts: state.alerts.remove(alert)
                triggered_something = True

def generate_369_levels(ltp, weekly_close):
    if weekly_close <= 0: return []
    levels = []
    pattern = [30, 60, 90] if weekly_close > 3333 else [3, 6, 9]
    # Resistance
    curr = weekly_close
    for i in range(10):
        step = pattern[i % 3]
        curr += step
        if curr > ltp: levels.append({"price": round(curr, 2), "type": "ABOVE"})
    # Support
    curr = weekly_close
    for i in range(10):
        step = pattern[i % 3]
        curr -= step
        if curr < ltp: levels.append({"price": round(curr, 2), "type": "BELOW"})
    return levels

# --- UI MAIN ---
def main(page: ft.Page):
    page.title = "Trade Yantra"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.window_width = 400
    page.window_height = 800
    page.assets_dir = "assets"
    if os.path.exists("assets/icon.png"): page.window_icon = "assets/icon.png"
    
    config = load_config()
    state.api_key = config.get("api_key", "")
    state.client_id = config.get("client_id", "")
    state.watchlist = config.get("watchlist", [])
    
    load_scrips(page)

    api_input = ft.TextField(label="SmartAPI Key", password=True, value=state.api_key)
    client_input = ft.TextField(label="Client ID", value=state.client_id)
    pass_input = ft.TextField(label="Password", password=True)
    totp_input = ft.TextField(label="TOTP Secret", password=True)
    login_status = ft.Text("", color="red")
    login_progress = ft.ProgressRing(visible=False)

    def handle_login(e):
        login_progress.visible = True
        page.update()
        success, msg = angel_login(api_input.value, client_input.value, pass_input.value, totp_input.value)
        if success:
            state.api_key = api_input.value
            state.client_id = client_input.value
            save_config()
            state.connected = True
            start_websocket(page)
            fetch_initial_ltp() 
            page.go("/app")
        else:
            login_status.value = f"Error: {msg}"
        login_progress.visible = False
        page.update()

    login_view = ft.Column([
        ft.Text("Trade Yantra", size=32, weight="bold", color="#667EEA"),
        ft.Text("Smart Trading Alerts", size=14, color="grey"),
        ft.Divider(height=20, color="transparent"),
        api_input, client_input, pass_input, totp_input,
        ft.ElevatedButton("Login", on_click=handle_login, bgcolor="#667EEA", color="white", height=45),
        ft.Row([login_progress, login_status])
    ], alignment="center", horizontal_alignment="center", spacing=15)

    body_container = ft.Container(expand=True, padding=10)

    def get_watchlist_view():
        controls = []
        
        # Feed Status Label
        state.feed_status_control = ft.Text(f"Feed: {state.live_feed_status}", 
                                           color="#F56565" if state.live_feed_status != "CONNECTED" else "#48BB78", 
                                           size=12, weight="bold")

        search_icon = "search"
        search_disabled = not state.master_loaded
        
        controls.append(ft.Row([
            state.feed_status_control,
            ft.Row([
                ft.IconButton(search_icon, on_click=open_search_bs, disabled=search_disabled, icon_color="#667EEA"),
                ft.IconButton("refresh", on_click=lambda e: refresh_all_data(page), icon_color="#667EEA")
            ])
        ], alignment="spaceBetween"))
        
        # --- FILTERS & SORTING RESTORED ---
        def on_filter_change(e):
            state.filter_symbol = e.control.value.upper() if e.control.value else ""
            update_view()
        def on_min_price_change(e):
            state.filter_min_price = e.control.value
            update_view()
        def on_max_price_change(e):
            state.filter_max_price = e.control.value
            update_view()
        def on_sort_change(e):
            state.sort_by = e.control.value
            update_view()
        def clear_all(e):
            state.filter_symbol = ""
            state.filter_min_price = ""
            state.filter_max_price = ""
            update_view()

        controls.append(ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.TextField(label="Filter Symbol", value=state.filter_symbol, dense=True, 
                                on_change=on_filter_change, expand=True, border_color="#2D3748"),
                    ft.Dropdown(label="Sort", value=state.sort_by, dense=True, width=140,
                               on_change=on_sort_change, border_color="#2D3748",
                               options=[
                                   ft.dropdown.Option("none", "Default"),
                                   ft.dropdown.Option("sym_az", "Symbol A-Z"),
                                   ft.dropdown.Option("sym_za", "Symbol Z-A"),
                                   ft.dropdown.Option("price_low", "Price Low"),
                                   ft.dropdown.Option("price_high", "Price High"),
                               ])
                ]),
                ft.Row([
                    ft.TextField(label="Min Price", value=state.filter_min_price, dense=True,
                                width=90, on_change=on_min_price_change, keyboard_type=ft.KeyboardType.NUMBER,
                                border_color="#2D3748"),
                    ft.TextField(label="Max Price", value=state.filter_max_price, dense=True,
                                width=90, on_change=on_max_price_change, keyboard_type=ft.KeyboardType.NUMBER,
                                border_color="#2D3748"),
                    ft.TextButton("Clear", on_click=clear_all, style=ft.ButtonStyle(color="#667EEA"))
                ])
            ]),
            padding=12,
            bgcolor="#222844",
            border_radius=10,
            border=ft.border.all(1, "#2D3748")
        ))
        
        # --- FILTERING LOGIC ---
        filtered_list = state.watchlist
        if state.filter_symbol:
            filtered_list = [s for s in filtered_list if state.filter_symbol in s['symbol']]
        if state.filter_min_price:
            try:
                min_p = float(state.filter_min_price)
                filtered_list = [s for s in filtered_list if s.get('ltp', 0) >= min_p]
            except: pass
        if state.filter_max_price:
            try:
                max_p = float(state.filter_max_price)
                filtered_list = [s for s in filtered_list if s.get('ltp', 0) <= max_p]
            except: pass
            
        # Sorting
        if state.sort_by == "sym_az":
            filtered_list = sorted(filtered_list, key=lambda x: x['symbol'])
        elif state.sort_by == "sym_za":
            filtered_list = sorted(filtered_list, key=lambda x: x['symbol'], reverse=True)
        elif state.sort_by == "price_low":
            filtered_list = sorted(filtered_list, key=lambda x: x.get('ltp', 0))
        elif state.sort_by == "price_high":
            filtered_list = sorted(filtered_list, key=lambda x: x.get('ltp', 0), reverse=True)
        
        lv = ft.ListView(expand=True, spacing=10)
        for stock in filtered_list:
            if 'ltp_control' not in stock:
                stock['ltp_control'] = ft.Text("₹0.00", weight="bold", color="#48BB78", size=15)
                stock['wc_control'] = ft.Text("WC: 0.00", size=10, color="#A0AEC0")
                stock['loader_control'] = ft.ProgressRing(width=16, height=16, color="#667EEA", visible=False)
            
            stock['ltp_control'].value = f"₹{stock.get('ltp', 0):.2f}"
            stock['wc_control'].value = f"WC: {stock.get('wc', 0):.2f}"
            stock['loader_control'].visible = stock.get('loading', False)
            
            lv.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Text(stock['symbol'], weight="bold", size=14),
                            ft.Text(stock['token'], size=10, color="#A0AEC0")
                        ]),
                        ft.Row([
                            ft.Column([ft.Row([stock['loader_control'], stock['ltp_control']]), stock['wc_control']], alignment="end"),
                            ft.IconButton("delete", icon_color="#F56565", on_click=lambda e, t=stock['token']: remove_stock(t))
                        ])
                    ], alignment="spaceBetween"),
                    padding=12,
                    bgcolor="#222844",
                    border_radius=8,
                    border=ft.border.all(1, "#2D3748")
                )
            )
        controls.append(lv)
        return ft.Column(controls, expand=True)

    def remove_stock(token):
        state.watchlist = [s for s in state.watchlist if s['token'] != token]
        save_config()
        update_view()

    # --- ALERTS VIEW RESTORED ---
    def get_alerts_view():
        controls = []
        controls.append(ft.Container(
            content=ft.Column([
                ft.Text("Strategy: 3-6-9 Logic", weight="bold"),
                ft.ElevatedButton("Auto-Generate Levels", on_click=generate_alerts_ui, 
                                 bgcolor="#667EEA", color="white"),
                ft.Switch(label="Pause Monitoring", value=state.is_paused, on_change=toggle_pause,
                         active_color="#667EEA")
            ], spacing=10),
            padding=12, bgcolor="#222844", border_radius=10, border=ft.border.all(1, "#2D3748")
        ))
        controls.append(ft.Divider(height=10, color="transparent"))
        lv = ft.ListView(expand=True, spacing=8)
        if not state.alerts: 
            lv.controls.append(ft.Text("No active alerts", color="#A0AEC0"))
        for alert in state.alerts:
            col = "#48BB78" if alert['condition'] == "ABOVE" else "#F56565"
            icon = "trending_up" if alert['condition'] == "ABOVE" else "trending_down"
            lv.controls.append(ft.Container(
                content=ft.Row([
                    ft.Row([
                        ft.Icon(icon, color=col, size=20),
                        ft.Column([
                            ft.Text(alert['symbol'], weight="bold"),
                            ft.Text(f"Target: ₹{alert['price']}", size=12, color="#A0AEC0")
                        ], spacing=2)
                    ], spacing=10),
                    ft.IconButton("delete", icon_color="#F56565", 
                                 on_click=lambda e, uid=alert['id']: delete_alert(uid))
                ], alignment="spaceBetween"),
                padding=12, bgcolor="#222844", border_radius=8, border=ft.border.all(1, "#2D3748")
            ))
        controls.append(lv)
        return ft.Column(controls, expand=True)

    def generate_alerts_ui(e):
        count = 0
        for stock in state.watchlist:
            if stock.get('wc', 0) > 0:
                lvls = generate_369_levels(stock.get('ltp', 0), stock['wc'])
                for l in lvls:
                    if not any(a['token'] == stock['token'] and a['price'] == l['price'] for a in state.alerts):
                        state.alerts.append({"id": str(uuid.uuid4()), "symbol": stock['symbol'], "token": stock['token'], "price": l['price'], "condition": l['type']})
                        count += 1
        if count > 0: state.logs.insert(0, {"time": "SYS", "symbol": "AUTO", "msg": f"Generated {count} alerts"})
        update_view()

    def delete_alert(uid):
        state.alerts = [a for a in state.alerts if a['id'] != uid]
        update_view()

    def toggle_pause(e): state.is_paused = e.control.value

    def get_logs_view(): 
        lv = ft.ListView(expand=True)
        for log in state.logs: lv.controls.append(ft.Container(content=ft.Row([ft.Text(log['time'], size=10, color="grey"), ft.Text(log['symbol'], weight="bold", width=80), ft.Text(log['msg'], expand=True)]), padding=5, border=ft.border.only(bottom=ft.BorderSide(1, "#333333"))))
        return ft.Column([ft.Text("Activity Log", size=20), ft.Divider(), lv], expand=True)

    def open_search_bs(e):
        search_field = ft.TextField(label="Symbol", autofocus=True, on_change=lambda e: run_search(e.data))
        results_list = ft.ListView(expand=True)
        def run_search(q):
            q = q.upper()
            results_list.controls.clear()
            if len(q) > 2:
                matches = [s for s in state.scrips if s['symbol'].startswith(q)][:15]
                for m in matches:
                    results_list.controls.append(ft.ListTile(title=ft.Text(m['symbol']), on_click=lambda e, item=m: add_stock(item)))
            bs.update()
        def add_stock(item):
            if not any(s['token'] == item['token'] for s in state.watchlist):
                new_stock = {"symbol": item['symbol'], "token": item['token'], "exch_seg": item['exch_seg'], "ltp": 0.0, "wc": 0.0, "loading": True}
                state.watchlist.append(new_stock)
                save_config()
                api_job_queue.put((fetch_historical_data_task, [new_stock], page))
                if state.sws and state.live_feed_status == "CONNECTED": 
                     try: state.sws.subscribe("add", 1, [{"exchangeType": 1, "tokens": [item['token']]}])
                     except: pass
            page.close(bs)
            update_view()
        bs = ft.BottomSheet(ft.Container(ft.Column([search_field, results_list], expand=True), padding=20, height=500), open=True)
        page.overlay.append(bs)
        page.update()

    def update_view():
        if state.current_view == "watchlist": body_container.content = get_watchlist_view()
        elif state.current_view == "alerts": body_container.content = get_alerts_view()
        elif state.current_view == "logs": body_container.content = get_logs_view()
        try: page.update()
        except: pass

    def nav_change(e):
        state.current_view = e.control.data
        update_view()

    nav_row = ft.Row([
        ft.IconButton("list", data="watchlist", on_click=nav_change), 
        ft.IconButton("notifications", data="alerts", on_click=nav_change),
        ft.IconButton("history", data="logs", on_click=nav_change)
    ], alignment="spaceAround")

    def route_change(e):
        page.views.clear()
        page.views.append(ft.View("/", [ft.Container(content=login_view, alignment=ft.alignment.center, expand=True)]))
        if page.route == "/app":
            page.views.append(ft.View("/app", [
                ft.AppBar(title=ft.Text("Trade Yantra"), bgcolor="#1A1F3A"),
                ft.Container(content=body_container, bgcolor="#0A0E27", expand=True),
                ft.Container(content=nav_row, bgcolor="#1A1F3A", padding=10)
            ]))
            update_view()
            
            # --- UI TIMER: UPDATES PRICES AND STATUS LABEL ---
            def refresh_watchlist_timer():
                while True:
                    time.sleep(1.0)
                    if state.current_view == "watchlist" and page.route == "/app":
                        try:
                            # 1. Update Feed Status
                            if state.feed_status_control:
                                state.feed_status_control.value = f"Feed: {state.live_feed_status}"
                                state.feed_status_control.color = "#48BB78" if state.live_feed_status == "CONNECTED" else "#F56565"
                            
                            # 2. Update Stock Prices from State to UI Control
                            for stock in state.watchlist:
                                if 'ltp_control' in stock and stock.get('ltp'):
                                    new_val = f"₹{stock['ltp']:.2f}"
                                    if stock['ltp_control'].value != new_val:
                                        stock['ltp_control'].value = new_val
                                    stock['loader_control'].visible = stock.get('loading', False)
                            
                            page.update()
                        except Exception as e:
                            print(f"Timer stopped: {e}")
                            break
            
            threading.Thread(target=refresh_watchlist_timer, daemon=True).start()

    page.on_route_change = route_change
    page.go(page.route)

if __name__ == "__main__":
    ft.app(target=main)