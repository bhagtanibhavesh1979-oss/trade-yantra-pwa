"""
WebSocket Manager - Handles Angel One SmartAPI WebSocket
Maintains connection and broadcasts to frontend clients
"""
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
import threading
import struct
import asyncio
import json
from typing import Dict, List, Callable, Optional
from services.alert_service import check_alert_trigger, create_alert_log

class WebSocketManager:
    def __init__(self):
        self.connections: Dict[str, SmartWebSocketV2] = {}  # session_id -> websocket
        self.token_maps: Dict[str, Dict] = {}  # session_id -> {token -> stock_data}
        self.broadcast_callbacks: Dict[str, Callable] = {}  # session_id -> callback
        self.lock = threading.Lock()

    def start_websocket(self, session_id: str, jwt_token: str, api_key: str, 
                       client_id: str, feed_token: str, watchlist: List[Dict],
                       broadcast_callback: Callable):
        """
        Start WebSocket connection for a session
        """
        try:
            sws = SmartWebSocketV2(jwt_token, api_key, client_id, feed_token)
        except Exception as e:
            print(f"WebSocket Init Error for {session_id}: {e}")
            return False

        # Create token map
        token_map = {str(s['token']): s for s in watchlist}
        
        with self.lock:
            self.connections[session_id] = sws
            self.token_maps[session_id] = token_map
            self.broadcast_callbacks[session_id] = broadcast_callback

        def on_data(wsapp, message):
            """Handle incoming price data"""
            try:
                # JSON format
                if isinstance(message, (list, dict)):
                    if isinstance(message, dict):
                        message = [message]
                    
                    for tick in message:
                        token = tick.get('token') or tick.get('tk')
                        raw_price = tick.get('last_traded_price') or tick.get('ltp') or tick.get('c')
                        
                        if token and raw_price is not None:
                            stock = token_map.get(str(token))
                            if stock:
                                stock['ltp'] = float(raw_price) / 100.0 if 'last_traded_price' in tick else float(raw_price)
                                # Broadcast update
                                broadcast_callback(session_id, {
                                    'type': 'price_update',
                                    'data': {
                                        'token': str(token),
                                        'symbol': stock['symbol'],
                                        'ltp': stock['ltp']
                                    }
                                })
                
                # Binary format
                elif isinstance(message, bytes) and len(message) > 50:
                    try:
                        token_bytes = message[2:27]
                        token = token_bytes.replace(b'\x00', b'').decode('utf-8')
                        ltp_bytes = message[43:51]
                        ltp_paise = struct.unpack('<q', ltp_bytes)[0]
                        real_price = ltp_paise / 100.0
                        
                        stock = token_map.get(str(token))
                        if stock:
                            stock['ltp'] = real_price
                            # Broadcast update
                            broadcast_callback(session_id, {
                                'type': 'price_update',
                                'data': {
                                    'token': str(token),
                                    'symbol': stock['symbol'],
                                    'ltp': real_price
                                }
                            })
                    except:
                        pass
            except Exception as e:
                print(f"WebSocket data error: {e}")

        def on_open(wsapp):
            """Handle connection open"""
            print(f"WebSocket Connected for {session_id}")
            broadcast_callback(session_id, {
                'type': 'status',
                'data': {'status': 'CONNECTED'}
            })
            
            # Subscribe to tokens
            token_list_str = [str(item['token']) for item in watchlist]
            if token_list_str:
                try:
                    sws.subscribe("watchlist", 3, [{"exchangeType": 1, "tokens": token_list_str}])
                    print(f"Subscribed to {len(token_list_str)} tokens for {session_id}")
                except Exception as e:
                    print(f"Subscribe error: {e}")

        def on_close(wsapp, code, reason):
            """Handle connection close"""
            print(f"WebSocket Closed for {session_id}: {code} {reason}")
            broadcast_callback(session_id, {
                'type': 'status',
                'data': {'status': 'DISCONNECTED'}
            })

        def on_error(wsapp, error):
            """Handle WebSocket error"""
            print(f"WebSocket Error for {session_id}: {error}")
            broadcast_callback(session_id, {
                'type': 'status',
                'data': {'status': 'ERROR', 'error': str(error)}
            })

        sws.on_data = on_data
        sws.on_open = on_open
        sws.on_close = on_close
        sws.on_error = on_error

        # Start connection in background thread
        threading.Thread(target=sws.connect, daemon=True).start()
        
        return True

    def subscribe_token(self, session_id: str, token: str, stock_data: Dict):
        """
        Subscribe to a new token for an existing session
        """
        with self.lock:
            if session_id in self.connections and session_id in self.token_maps:
                self.token_maps[session_id][str(token)] = stock_data
                try:
                    sws = self.connections[session_id]
                    sws.subscribe("add", 3, [{"exchangeType": 1, "tokens": [str(token)]}])
                    print(f"Subscribed to token {token} for {session_id}")
                except Exception as e:
                    print(f"Subscribe error for token {token}: {e}")

    def unsubscribe_token(self, session_id: str, token: str):
        """
        Unsubscribe from a token
        """
        with self.lock:
            if session_id in self.token_maps:
                if str(token) in self.token_maps[session_id]:
                    del self.token_maps[session_id][str(token)]
                # Note: SmartAPI doesn't have explicit unsubscribe

    def stop_websocket(self, session_id: str):
        """
        Stop WebSocket connection for a session
        """
        with self.lock:
            if session_id in self.connections:
                try:
                    # SmartAPI doesn't have explicit close, just remove reference
                    del self.connections[session_id]
                    del self.token_maps[session_id]
                    del self.broadcast_callbacks[session_id]
                    print(f"Stopped WebSocket for {session_id}")
                except Exception as e:
                    print(f"Error stopping WebSocket for {session_id}: {e}")

    def stop_all(self):
        """
        Stop all WebSocket connections
        """
        with self.lock:
            for session_id in list(self.connections.keys()):
                try:
                    del self.connections[session_id]
                    del self.token_maps[session_id]
                    del self.broadcast_callbacks[session_id]
                except:
                    pass
            print("Stopped all WebSocket connections")

# Global WebSocket manager instance
ws_manager = WebSocketManager()
